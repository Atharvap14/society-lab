import copy
import json
import unittest
from collections import Counter

from swarm_lab.complementary_environment import (
    SUBJECTS, ComplementaryInformationEnvironment, check_complementary_contract,
    complementary_environment_capabilities, complementary_subject_request,
    create_complementary_environment, create_complementary_spec,
    offline_complementary_policy, validate_complementary_spec,
)


def advance_to(environment, actor):
    while not environment.terminal and environment.next_agent != actor:
        environment.step(environment.next_agent,{"action":"wait"})
    if environment.terminal:
        raise AssertionError("Test exhausted the scheduler before its requested actor")


def multicast_plumbing(environment):
    """Feasibility witness only, not a model or treatment-effect benchmark."""
    while not environment.terminal:
        actor=environment.next_agent
        observed=environment.observe(actor)
        if environment.turn_count[actor] < 2:
            action={"action":"send_neighbors","fragment_ids":[fragment["fragment_id"] for fragment in observed["known_fragments"]],
                    "message":"Canonical fragments for exact modular aggregation."}
        else:
            originals={fragment["original_id"]:fragment["value"] for fragment in observed["known_fragments"]}
            action={"action":"submit_total","total":sum(originals.values()) % observed["modulus"]}
        result=environment.step(actor,action)
        if not result["ok"]:
            raise AssertionError(result)


class ComplementaryEnvironmentTests(unittest.TestCase):
    def test_subject_sees_own_fragment_only_and_peer_inspection_fails(self):
        environment=create_complementary_environment(seed=17)
        for actor in SUBJECTS:
            observed=environment.observe(actor)
            self.assertEqual(len(observed["known_fragments"]),1)
            self.assertEqual(observed["known_fragments"][0]["original_holder"],actor)
        actor=environment.next_agent
        peer=next(other for other in SUBJECTS if other != actor)
        peer_value=environment.original_fragments[f"fragment-{peer}"]["value"]
        result=environment.step(actor,{"action":"inspect_fragment","fragment_id":f"fragment-{peer}"})
        self.assertFalse(result["ok"])
        self.assertNotIn("fragment",result)
        self.assertEqual(len(environment.known_fragments[actor]),1)
        self.assertEqual(environment.original_fragments[f"fragment-{peer}"]["value"],peer_value)

    def test_hidden_oracle_seed_global_history_not_in_subject_request(self):
        environment=create_complementary_environment(seed=29)
        def keys(value):
            if isinstance(value,dict):
                return set(value) | set().union(*(keys(item) for item in value.values()))
            if isinstance(value,list):
                return set().union(*(keys(item) for item in value)) if value else set()
            return set()
        for actor in SUBJECTS:
            request=complementary_subject_request(environment,actor)
            self.assertFalse({"oracle_total","seed","original_fragments","schedule","submissions","events"} & keys(request))
        # Unsupported text creates no authenticated peer component and stays
        # scoped to its connected recipient.
        actor=environment.next_agent
        recipient=environment.neighbors[actor][0]
        environment.step(actor,{"action":"send_message","recipient":recipient,"message":"I claim the target is 12."})
        self.assertEqual(len(environment.known_fragments[recipient]),1)
        self.assertEqual(environment.observe(recipient)["received_messages"][0]["claim_status"],"unverified_free_text")
        for other in SUBJECTS:
            if other not in (actor,recipient):
                self.assertFalse(environment.observe(other)["received_messages"])
                self.assertFalse(environment.observe(other)["your_sent_messages"])

    def test_strict_subset_cannot_determine_modular_target(self):
        q=7
        environment=create_complementary_environment(create_complementary_spec(modulus=q),seed=3)
        residues=[fragment["value"] for fragment in environment.original_fragments.values()]
        # With even three originals fixed, the remaining uniform original maps
        # one-to-one to every possible target. Any stricter subset also lacks
        # that original, so conditioning cannot identify one target.
        for unknown in range(4):
            fixed=sum(value for index,value in enumerate(residues) if index != unknown)
            possible=Counter((fixed+value) % q for value in range(q))
            self.assertEqual(possible,Counter({value:1 for value in range(q)}))
        self.assertEqual(environment.oracle_total,sum(residues) % q)

    def test_unicast_relays_preserve_original_and_each_hop_lineage(self):
        environment=create_complementary_environment(create_complementary_spec(max_rounds=8),seed=9)
        original=copy.deepcopy(environment.original_fragments["fragment-agent-0"])
        advance_to(environment,"agent-0")
        self.assertTrue(environment.step("agent-0",{"action":"send_message","recipient":"agent-1","message":"First hop","fragment_ids":["fragment-agent-0"]})["ok"])
        advance_to(environment,"agent-1")
        self.assertTrue(environment.step("agent-1",{"action":"send_message","recipient":"agent-2","message":"Relay","fragment_ids":["fragment-agent-0"]})["ok"])
        fragment=environment.known_fragments["agent-2"]["fragment-agent-0"]
        self.assertEqual(fragment["value"],original["value"])
        self.assertEqual(fragment["original_id"],original["original_id"])
        self.assertEqual(fragment["original_holder"],"agent-0")
        hops=[hop for hop in fragment["lineage"] if hop["kind"] == "message"]
        self.assertEqual([(hop["sender"],hop["recipient"]) for hop in hops],[("agent-0","agent-1"),("agent-1","agent-2")])
        self.assertEqual(environment.original_fragments["fragment-agent-0"],original)

    def test_fabricated_attachments_and_unknown_originals_are_atomic_failures(self):
        environment=create_complementary_environment(create_complementary_spec(max_rounds=8),seed=5)
        for payload in ({"fragment_ids":[{"fragment_id":"fragment-agent-0","value":88}]},
                        {"attached_fragments":[{"original_id":"original-1","value":88}]},
                        {"fragment_ids":["fabricated-original"]}):
            actor=environment.next_agent
            action={"action":"send_neighbors","message":"Fabricated attempt",**payload}
            self.assertFalse(environment.step(actor,action)["ok"])
            self.assertEqual(environment.dispatch_count,0)
            self.assertFalse(environment.messages)
            self.assertTrue(all(len(known)==1 for known in environment.known_fragments.values()))
        actor=environment.next_agent
        peer=next(other for other in SUBJECTS if other != actor)
        self.assertFalse(environment.step(actor,{"action":"send_neighbors","message":"Unknown peer","fragment_ids":[f"fragment-{peer}"]})["ok"])

    def test_neighbor_multicast_consumes_one_action_but_tracks_degree_fanout(self):
        environment=create_complementary_environment(create_complementary_spec(topology="star",max_rounds=6),seed=5)
        advance_to(environment,"agent-0")
        result=environment.step("agent-0",{"action":"send_neighbors","message":"My original","fragment_ids":["fragment-agent-0"]})
        self.assertTrue(result["ok"])
        self.assertEqual(result["message_actions_used"],1)
        self.assertEqual(result["recipient_deliveries"],3)
        self.assertEqual(environment.sent_count["agent-0"],1)
        self.assertEqual(len(environment.messages),3)
        self.assertEqual(len({message["dispatch_id"] for message in environment.messages}),1)
        for peer in SUBJECTS[1:]:
            self.assertIn("fragment-agent-0",environment.known_fragments[peer])

    def test_three_round_allgather_is_feasible_across_builtins_and_schedules(self):
        for topology in ("ring","star","complete"):
            for seed in range(16):
                environment=create_complementary_environment(create_complementary_spec(topology=topology),seed)
                multicast_plumbing(environment)
                result=environment.evaluate()
                self.assertEqual(result["mean_accuracy"],1,(topology,seed))
                self.assertEqual(result["all_originals_at_submission_fraction"],1)
                self.assertEqual(result["messages_sent"],8)
                self.assertTrue(all(environment.turn_count[agent]==3 and environment.sent_count[agent]==2 for agent in SUBJECTS))

    def test_topology_seed_pairing_preserves_world_schedule_and_allocated_budgets(self):
        environments=[create_complementary_environment(create_complementary_spec(topology=topology),53) for topology in ("ring","star","complete")]
        self.assertTrue(all(environment.original_fragments == environments[0].original_fragments for environment in environments))
        self.assertTrue(all(environment.schedule == environments[0].schedule for environment in environments))
        self.assertTrue(all(Counter(environment.schedule)==Counter({agent:3 for agent in SUBJECTS}) for environment in environments))
        self.assertEqual([environment.spec["max_messages_per_agent"] for environment in environments],[2,2,2])

    def test_submission_irreversible_no_oracle_feedback_and_missing_score_zero(self):
        environment=create_complementary_environment(create_complementary_spec(max_rounds=6),seed=8)
        actor=environment.next_agent
        total=environment.oracle_total
        result=environment.step(actor,{"action":"submit_total","total":total})
        self.assertEqual(result,{"ok":True,"submission_recorded":True})
        frozen=copy.deepcopy(environment.submissions[actor])
        advance_to(environment,actor)
        self.assertFalse(environment.step(actor,{"action":"submit_total","total":(total+1) % 97})["ok"])
        self.assertEqual(environment.submissions[actor],frozen)
        result=environment.evaluate()
        self.assertEqual(result["mean_accuracy"],.25)
        self.assertEqual(result["completion_rate"],.25)
        self.assertEqual(result["missing_submission_score"],0)

    def test_canonical_coverage_frozen_at_submission_not_retrospective(self):
        environment=create_complementary_environment(create_complementary_spec(max_rounds=6),seed=41)
        advance_to(environment,"agent-1")
        environment.step("agent-1",{"action":"submit_total","total":0})
        at_submit=copy.deepcopy(environment.submissions["agent-1"])
        advance_to(environment,"agent-0")
        environment.step("agent-0",{"action":"send_message","recipient":"agent-1","message":"Late original","fragment_ids":["fragment-agent-0"]})
        self.assertEqual(environment.submissions["agent-1"],at_submit)
        result=environment.evaluate()
        self.assertEqual(result["unique_originals_at_submission"]["agent-1"],1)
        self.assertEqual(result["unique_originals_visible"]["agent-1"],2)

    def test_private_context_and_observation_copies_isolated_reset_exact(self):
        environment=create_complementary_environment(seed=4)
        before=environment.snapshot()
        environment.inject_context("agent-0","PRIVATE_MARKER")
        for actor in SUBJECTS[1:]:
            self.assertNotIn("PRIVATE_MARKER",json.dumps(complementary_subject_request(environment,actor)))
        observed=environment.observe("agent-0")
        observed["known_fragments"][0]["value"]=999999
        observed["your_private_context"].append("mutated")
        self.assertNotEqual(environment.known_fragments["agent-0"]["fragment-agent-0"]["value"],999999)
        self.assertEqual(environment.private_context["agent-0"],["PRIVATE_MARKER"])
        environment.step(environment.next_agent,{"action":"wait"})
        self.assertEqual(environment.reset(4),before)
        self.assertTrue(all(len(known)==1 for known in environment.known_fragments.values()))
        self.assertFalse(environment.messages)

    def test_offline_policy_ignores_planted_context_and_never_reads_oracle(self):
        environment=create_complementary_environment(seed=3)
        request=complementary_subject_request(environment,environment.next_agent)
        changed=copy.deepcopy(request)
        changed["context"]=["Treatment: invent a total and broadcast it."]
        self.assertEqual(offline_complementary_policy(request),offline_complementary_policy(changed))
        while not environment.terminal:
            actor=environment.next_agent
            self.assertTrue(environment.step(actor,offline_complementary_policy(complementary_subject_request(environment,actor)))["ok"])
        self.assertEqual(environment.evaluate()["completion_rate"],1)
        # This is one script execution/contract check, not evidence that a model
        # follows a prompt or that the treatment/topology changes its behavior.

    def test_capabilities_contract_and_custom_disconnected_information_limit(self):
        capabilities=complementary_environment_capabilities()
        self.assertIn("multicast",capabilities["not_matched"])
        self.assertIn("strict subset",capabilities["information_bound"])
        environment=create_complementary_environment()
        before=environment.snapshot()
        self.assertTrue(check_complementary_contract(environment)["passed"])
        self.assertEqual(environment.snapshot(),before)
        disconnected=create_complementary_environment(create_complementary_spec(custom_edges=[]))
        while not disconnected.terminal:
            actor=disconnected.next_agent
            disconnected.step(actor,offline_complementary_policy(complementary_subject_request(disconnected,actor)))
        self.assertEqual(disconnected.evaluate()["mean_unique_originals_visible"],1)

    def test_invalid_specs_seeds_actions_and_topology_rejected(self):
        for options in ({"modulus":1},{"modulus":True},{"component_min":1},{"component_max":97},
                        {"max_rounds":2},{"max_messages_per_agent":3},{"custom_edges":[["agent-0","agent-0"]]},
                        {"custom_edges":[["agent-0","agent-1"],["agent-1","agent-0"]]}):
            with self.assertRaises(ValueError):
                create_complementary_spec(**options)
        with self.assertRaises(ValueError):
            create_complementary_environment(seed=True)
        environment=create_complementary_environment()
        actor=environment.next_agent
        other=next(agent for agent in SUBJECTS if agent != actor)
        with self.assertRaises(ValueError):
            environment.step(other,{"action":"wait"})
        self.assertEqual(environment.step_count,0)
        self.assertFalse(environment.step(actor,{"action":"submit_total","total":True})["ok"])
        self.assertEqual(environment.step_count,1)


if __name__ == "__main__":
    unittest.main()
