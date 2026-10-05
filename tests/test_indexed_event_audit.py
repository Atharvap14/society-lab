"""Authenticated-index projections are not fresh raw reads or causal exposure."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab.dataset import normalize_message
from swarm_lab.event_source_index import _project
from swarm_lab.indexed_event_audit import audit_indexed_event_matches, _hash, QUERY_COMBINATION

def uid(n): return f"00000000-0000-0000-0000-{n:012x}"
AGENT, ROOM, CHAT = uid(10),uid(20),uid(30)
REFS={name:{"id":name+"-fixture","version":1,"hash":"a"*64} for name in ("dataset","discovery","selected_audit")}
WINDOWS=[{"id":"window-fixture","room_id":ROOM,"start":"2026-01-01T00:00:00Z","end_exclusive":"2026-01-01T01:00:00Z","original_metric":.5}]

def raw_event(number=1, action="AGENT_TALK", **overrides):
    data={"actionType":action,"speakerId":AGENT,"roomId":ROOM,"messageId":CHAT,"content":" Untrimmed fixture text. ",**overrides}
    return {"id":uid(number),"event_index":number,"created_at":"2026-01-01 00:30:00.065551","data":data}

def normalized(number=30, **overrides):
    raw={"id":uid(number),"agent_speaker_id":AGENT,"speaker_type":"agent","room_id":ROOM,"content":" Untrimmed fixture text. ","created_at":"2026-01-01 00:30:00",**overrides}
    return normalize_message(raw,source=Path("fixture-chat.jsonl").resolve(),line=number)

def packet(events=(), *, complete=True, truncated=False, message_ids=None, windows=None, action_types=None):
    source_path=str(Path("fixture-events.jsonl").resolve())
    rows=[]
    for line,raw in enumerate(events,1):
        record=_project(raw)
        rows.append({"record":record,"projection_sha256":_hash(record),"source":{"path":source_path,"table":"events","line":line,
            "record_sha256":_hash(raw),"raw_line_sha256":hashlib.sha256((json.dumps(raw)+"\n").encode()).hexdigest()}})
    return {"kind":"indexed_event_source_query","schema_version":"1.0","instrument_version":"bounded-event-source-index-v1","read_only":True,"model_calls":0,
        "index":{"path":str(Path("fixture-index.sqlite3").resolve()),"expected_file_sha256":"b"*64,"read_file_sha256":"b"*64,"post_query_file_sha256":"b"*64,
            "file_hash_authenticated":True,"bytes":4096,"internal_metadata_sha256":"d"*64,"implementation_hashes":{f:"c"*64 for f in ("event_source_index.py","source_scanner.py","source_links.py","source_workflow.py")}},
        "query":{"message_ids":message_ids,"windows":windows,"action_types":action_types,"max_rows":15000,"combination":QUERY_COMBINATION},
        "records":rows,"coverage":{"build_scan":{"complete_scan":complete,"source_eof_observed":complete,"stop_reason":"eof" if complete else "row_limit",
            "physical_rows_seen":len(rows),"indexed_rows":len(rows)},"query_complete":not truncated,"truncated":truncated,
            "matched_rows":len(rows)+(1 if truncated else 0),"returned_rows":len(rows)}}

class IndexedAuditTests(unittest.TestCase):
    def audit(self, events=None, chats=None, **kwargs):
        return audit_indexed_event_matches(packet([raw_event()] if events is None else events),[normalized()] if chats is None else chats,
            windows=kwargs.pop("windows",WINDOWS),source_refs=kwargs.pop("source_refs",REFS),**kwargs)

    def test_pure_exact_matching_preserves_two_hash_purposes_and_window_source_pins(self):
        p=packet([raw_event()]); chats=[normalized()]; before=copy.deepcopy((p,chats,WINDOWS,REFS))
        with patch("swarm_lab.store.Store.__init__",side_effect=AssertionError("No DB")),patch("sqlite3.connect",side_effect=AssertionError("No index read here")):
            result=audit_indexed_event_matches(p,chats,windows=WINDOWS,source_refs=REFS)
        self.assertEqual((p,chats,WINDOWS,REFS),before)
        m=result["emissions"][0]
        self.assertEqual(m["emission_status"],"matched"); self.assertEqual(m["match_label"],"indexed_emission_fields_matching_normalized_chat")
        self.assertEqual(m["normalized_compound_content_hash"],chats[0]["content_hash"])
        self.assertEqual(m["canonical_content_value_hash"],_hash(chats[0]["content"]))
        self.assertNotEqual(m["normalized_compound_content_hash"],m["canonical_content_value_hash"])
        self.assertEqual(m["parent_source"]["line"],30); self.assertEqual(result["windows"][0]["source_window_hash"],_hash(WINDOWS[0]))
        self.assertEqual(m["timestamp_difference_ms"],65.551)
        for key in ("receipt","exposure","consumption","causal_influence"): self.assertEqual(m[key],"unestablished")
        self.assertFalse(result["index_artifact_binding"]["original_event_bytes_reread"])
        self.assertEqual(result["model_calls"],0); self.assertEqual(result["database_writes"],0); self.assertFalse(result["status_promotion"])

    def test_actor_room_content_optional_message_and_raw_actor_conflicts_remain_conflicts(self):
        variants=[raw_event(speakerId=uid(11)),raw_event(roomId=uid(21)),raw_event(content="Trimmed or different"),raw_event(chatMessageId=uid(31)),raw_event(agentId=uid(11)),raw_event(speakerType="user")]
        for event in variants:
            with self.subTest(event_hash=_hash(event)):
                m=self.audit(events=[event])["emissions"][0]
                self.assertEqual(m["emission_status"],"conflict"); self.assertTrue(m["semantic_conflict_present"])
        c=normalized(); c["agent_speaker_id"]=uid(11)
        self.assertEqual(self.audit(chats=[c])["emissions"][0]["emission_status"],"conflict")
        c=normalized(); c["speaker_type"]="user"
        self.assertEqual(self.audit(chats=[c])["emissions"][0]["emission_status"],"conflict")

    def test_unknown_absent_null_fields_never_alias_or_match(self):
        for name,value in (("speakerId",None),("roomId",None),("content",None),("chatMessageId",None),("speakerType",None)):
            self.assertEqual(self.audit(events=[raw_event(**{name:value})])["emissions"][0]["emission_status"],"unknown")
        e=raw_event(); del e["data"]["speakerId"]
        self.assertEqual(self.audit(events=[e])["emissions"][0]["emission_status"],"unknown")
        c=normalized(); c["agent_id"]=None
        self.assertEqual(self.audit(chats=[c])["emissions"][0]["emission_status"],"unknown")

    def test_selected_denominator_agent_user_other_never_calls_user_missing_agent(self):
        human=normalized(31,speaker_type="user",agent_speaker_id=None,user_speaker_id=uid(11))
        other=normalized(32); other["speaker_type"]="unsupported"
        result=self.audit(chats=[normalized(),human,other]); counts=result["counts"]
        self.assertEqual(counts["selected_chat_by_speaker_type"],{"agent":1,"user":1,"other":1})
        self.assertEqual(counts["emission_statuses_by_speaker_type"]["agent"],{"matched":1,"unknown":0,"conflict":0})
        self.assertEqual(counts["emission_statuses_by_speaker_type"]["user"],{"matched":0,"unknown":1,"conflict":0})
        self.assertIn("not a missing-agent",result["emissions"][1]["emission_lookup_scope"])

    def test_explicit_source_speaker_type_must_agree_and_invalid_remains_unknown(self):
        for value,status in (("agent","matched"),("user","conflict"),(None,"unknown"),(True,"unknown"),("unrecognized","unknown")):
            with self.subTest(value=value): self.assertEqual(self.audit(events=[raw_event(speakerType=value)])["emissions"][0]["emission_status"],status)

    def test_duplicate_parents_and_children_are_ambiguous_consistent_checks_retained(self):
        c=normalized(); c2=copy.deepcopy(c); c2["source"]["line"]=31
        result=self.audit(chats=[c,c2])
        self.assertEqual([m["emission_status"] for m in result["emissions"]],["unknown","unknown"])
        self.assertEqual(result["emissions"][0]["ambiguity_status"],"duplicate_normalized_parent_id")
        self.assertEqual(result["emissions"][0]["candidate_checks"][0]["semantic_status"],"matching")
        result=self.audit(events=[raw_event(),raw_event(2)])
        m=result["emissions"][0]
        self.assertEqual(m["emission_status"],"unknown"); self.assertEqual(m["ambiguity_status"],"multiple_emission_records_for_message")
        self.assertEqual(len(m["candidate_checks"]),2)
        e2=raw_event(); e2["data"]["messageId"]=uid(31)
        result=self.audit(events=[raw_event(),e2],chats=[normalized(),normalized(31)])
        self.assertTrue(all(m["ambiguity_status"]=="duplicate_event_id" for m in result["emissions"]))
        self.assertTrue(all(m["emission_status"]=="unknown" for m in result["emissions"]))

    def test_missing_child_parent_and_out_of_scope_remain_unknown(self):
        result=self.audit(events=[])
        self.assertEqual(result["emissions"][0]["emission_status"],"unknown")
        result=self.audit(chats=[])
        self.assertEqual(result["projected_parent_links"][0]["status"],"absent_parent_in_supplied_dataset")
        result=self.audit(chats=[normalized(created_at="2026-01-01 02:00:00")])
        self.assertFalse(result["emissions"]); self.assertEqual(result["counts"]["out_of_scope_or_time_unresolved_chat_records"],1)
        self.assertEqual(result["projected_parent_links"][0]["status"],"outside_selected_chat_scope")
        e=raw_event(); del e["data"]["messageId"]; e["data"]["chatMessageId"]=CHAT
        result=self.audit(events=[e])
        self.assertEqual(result["emissions"][0]["emission_status"],"unknown")
        self.assertEqual(result["projected_parent_links"][0]["status"],"unknown_foreign_key")
        self.assertEqual(result["events"][0]["message_fk_identity_check"],"unknown")

    def test_partial_build_or_truncated_queries_never_establish_global_absence(self):
        for complete,truncated in ((False,False),(True,True)):
            p=packet([],complete=complete,truncated=truncated)
            if truncated: p["coverage"]["build_scan"].update(indexed_rows=1,physical_rows_seen=1)
            result=audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)
            self.assertEqual(result["emissions"][0]["emission_status"],"unknown")
            self.assertEqual(result["coverage"]["global_absence"],"unverified"); self.assertEqual(result["coverage"]["global_uniqueness"],"unverified")

    def test_actions_count_only_exact_window_room_time_and_explicit_actor(self):
        events=[raw_event(1,"WAIT",agentId=AGENT),raw_event(2,"PAUSE",agentId=AGENT,seconds=3.5),
            raw_event(3,"START_USING_COMPUTER",agentId=AGENT),raw_event(4,"STOP_USING_COMPUTER",agentId=AGENT),
            raw_event(5,"WAIT",agentId=AGENT,roomId=None),raw_event(6,"WAIT",agentId=None),raw_event(7,"PAUSE",agentId=AGENT,seconds=True)]
        result=self.audit(events=events)
        counts=result["windows"][0]
        self.assertEqual(counts["platform_actions"],{"WAIT":2,"PAUSE":2,"START_USING_COMPUTER":1,"STOP_USING_COMPUTER":1})
        self.assertEqual(counts["by_explicit_actor"][AGENT]["WAIT"],1)
        self.assertEqual(counts["pause_seconds_valid_records"],1); self.assertEqual(counts["pause_requested_seconds_sum"],3.5)
        self.assertIn("room_unmeasured_no_inference",result["events"][4]["unassigned_reasons"])
        self.assertEqual(result["events"][5]["actor_status"],"unknown")
        self.assertEqual(result["events"][3]["field_diagnostics"]["data.computerUseSessionId"]["presence"],"absent")

    def test_invalid_or_out_of_window_time_does_not_become_window_activity(self):
        for stamp in ("bad-date","2026-01-01 02:00:00"):
            e=raw_event(); e["created_at"]=stamp; e["event_index"]=True
            result=self.audit(events=[e]); row=result["events"][0]
            self.assertFalse(row["original_window_ids"])
            self.assertEqual(row["field_diagnostics"]["event_index"]["type_status"],"invalid")
            self.assertIsNone(row["event_index"])
            self.assertEqual(result["emissions"][0]["emission_status"],"matched")
            candidate=result["emissions"][0]["candidate_checks"][0]
            self.assertEqual(candidate["event_order_status"],"event_order_unknown")
            self.assertNotEqual(candidate["event_window_corroboration"],"same_explicit_room_time_window")
            if stamp=="bad-date": self.assertFalse(row["time_valid"]); self.assertIsNone(result["emissions"][0]["timestamp_difference_ms"])

    def test_explicit_offsets_normalize_while_naive_export_assumption_is_labeled(self):
        e=raw_event(); e["created_at"]="2026-01-01T01:30:00.065551+01:00"
        result=self.audit(events=[e])
        self.assertEqual(result["events"][0]["field_diagnostics"]["created_at"]["timezone_policy"],"explicit_offset_to_utc")
        self.assertEqual(result["emissions"][0]["timestamp_difference_ms"],65.551)
        self.assertEqual(self.audit()["events"][0]["field_diagnostics"]["created_at"]["timezone_policy"],"export_naive_assumed_utc")

    def test_file_hash_expected_read_post_and_flags_are_strict(self):
        mutations=[lambda p:p["index"].update(expected_file_sha256="d"*64),lambda p:p["index"].update(read_file_sha256="d"*64),
            lambda p:p["index"].update(post_query_file_sha256="d"*64),lambda p:p["index"].update(file_hash_authenticated=1),
            lambda p:p["index"].update(bytes=4096.0),lambda p:p.update(read_only=1),lambda p:p.update(model_calls=False)]
        for mutate in mutations:
            p=packet([raw_event()]); mutate(p)
            with self.subTest(mutation=repr(mutate)),self.assertRaises(ValueError): audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)

    def test_source_refs_positive_integer_versions_exact_hashes_and_identities(self):
        for value in (True,1.0,0,None):
            refs=copy.deepcopy(REFS); refs["dataset"]["version"]=value
            with self.subTest(version=value),self.assertRaises(ValueError): self.audit(source_refs=refs)
        refs=copy.deepcopy(REFS); refs["dataset"]["hash"]="bad"
        with self.assertRaises(ValueError): self.audit(source_refs=refs)
        refs=copy.deepcopy(REFS); refs["dataset"]["extra"]="ignored"
        with self.assertRaises(ValueError): self.audit(source_refs=refs)
        with self.assertRaises(ValueError): self.audit(source_refs={"dataset":REFS["dataset"]})

    def test_projection_hash_and_source_pins_type_bounds_reject(self):
        mutations=[lambda p:p["records"][0].update(projection_sha256="0"*64),
            lambda p:p["records"][0]["source"].update(record_sha256="invalid"),lambda p:p["records"][0]["source"].update(line=True),
            lambda p:p["records"][0]["source"].update(line=1.0),lambda p:p["records"][0]["source"].update(table="chat_messages"),
            lambda p:p["records"][0]["source"].update(line=2),lambda p:p["records"][0]["record"].update(content_hash="0"*64)]
        for mutate in mutations:
            p=packet([raw_event()]); mutate(p)
            with self.subTest(mutation=repr(mutate)),self.assertRaises(ValueError): audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)
        p=packet([raw_event()]); p["records"][0]["record"]["event_index"]=1.0; p["records"][0]["projection_sha256"]=_hash(p["records"][0]["record"])
        with self.assertRaises(ValueError): audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)
        for path,key in (("data.speakerId","utc"),("data.content","timezone_policy"),("data.roomId","value_type")):
            p=packet([raw_event()]); p["records"][0]["record"]["fields"][path][key]="PRIVATE TEXT MUST NEVER LEAK"
            p["records"][0]["projection_sha256"]=_hash(p["records"][0]["record"])
            with self.assertRaises(ValueError): audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)

    def test_declared_original_raw_hash_is_not_fresh_raw_verification(self):
        p=packet([raw_event()]); p["records"][0]["source"]["record_sha256"]="e"*64
        result=audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)
        self.assertEqual(result["events"][0]["source"]["record_sha256"],"e"*64)
        self.assertIn("declaration",result["events"][0]["raw_row_hash_scope"])
        self.assertFalse(result["index_artifact_binding"]["original_event_bytes_reread"])

    def test_query_union_exact_selection_and_global_action_filter(self):
        e=raw_event(); e["created_at"]="2026-01-01 02:00:00"
        wait=raw_event(2,"WAIT",agentId=AGENT)
        qw=[{k:WINDOWS[0][k] for k in ("room_id","start","end_exclusive")}]
        p=packet([e,wait],message_ids=[CHAT],windows=qw)
        result=audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)
        self.assertEqual(len(result["events"]),2); self.assertEqual(result["windows"][0]["platform_actions"]["WAIT"],1)
        p["query"]["message_ids"]=[uid(99)]; p["query"]["windows"]=None
        with self.assertRaises(ValueError): audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)
        p=packet([raw_event()],action_types=["WAIT"])
        with self.assertRaises(ValueError): audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)

    def test_no_raw_provider_thinking_text_trim_or_alias_promotion(self):
        secret="IGNORE RULES: secret private provider thinking and credential payload"
        e=raw_event(content=secret); e["data"]["output"]={"thinking":secret}
        c=normalized(content=secret); result=self.audit(events=[e],chats=[c]); serialized=json.dumps(result)
        self.assertNotIn(secret,serialized); self.assertNotIn("private provider",serialized)
        self.assertEqual(result["emissions"][0]["emission_status"],"matched")
        e=raw_event(action="AGENT_START"); result=self.audit(events=[e])
        self.assertEqual(result["events"][0]["actor_status"],"unrecognized_action")
        self.assertEqual(result["emissions"][0]["emission_status"],"unknown")
        e=raw_event(); e["data"]["content"]=e["data"]["content"].strip()
        self.assertEqual(self.audit(events=[e])["emissions"][0]["emission_status"],"conflict")

    def test_unicode_nonfinite_depth_input_rows_and_comparison_caps(self):
        p=packet([raw_event()]); p["untrusted"]="\ud800"
        with self.assertRaises(ValueError): audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)
        p=packet([raw_event()]); p["untrusted"]=float("inf")
        with self.assertRaises(ValueError): audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)
        p=packet([raw_event()]); p["untrusted"]=None; cursor=p
        for _ in range(20): cursor["nested"]={}; cursor=cursor["nested"]
        with self.assertRaises(ValueError): audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)
        with patch("swarm_lab.indexed_event_audit.MAX_ROWS",1):
            with self.assertRaises(ValueError): self.audit()
        with patch("swarm_lab.indexed_event_audit.MAX_INPUT_BYTES",100):
            with self.assertRaises(ValueError): self.audit()
        with patch("swarm_lab.indexed_event_audit.MAX_COMPARISONS",1):
            with self.assertRaises(ValueError): self.audit(events=[raw_event(),raw_event(2)])

    def test_window_bounds_identity_and_time_must_be_explicit(self):
        for mutate in (lambda w:w.update(room_id="main"),lambda w:w.update(start="2026-01-01 00:00:00"),
                       lambda w:w.update(end_exclusive=w["start"]),lambda w:w.update(id=True)):
            windows=copy.deepcopy(WINDOWS); mutate(windows[0])
            with self.assertRaises(ValueError): self.audit(windows=windows)
        with self.assertRaises(ValueError): self.audit(windows=WINDOWS+WINDOWS)
        with self.assertRaises(ValueError): self.audit(rules_version="guess-names")

    def test_actual_temporary_index_read_packet_interoperates_readonly(self):
        from swarm_lab.event_source_index import build_event_index,read_event_index
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"events.jsonl"; index=Path(directory)/"events.sqlite3"
            source.write_text(json.dumps(raw_event())+"\n"+json.dumps(raw_event(2,"WAIT",agentId=AGENT))+"\n",encoding="utf-8")
            build=build_event_index(source,index,max_rows=16,max_seconds=10)
            source_before=hashlib.sha256(source.read_bytes()).hexdigest(); index_before=hashlib.sha256(index.read_bytes()).hexdigest()
            p=read_event_index(index,expected_file_sha256=index_before,message_ids=[CHAT],windows=[{k:WINDOWS[0][k] for k in ("room_id","start","end_exclusive")}])
            result=audit_indexed_event_matches(p,[normalized()],windows=WINDOWS,source_refs=REFS)
            self.assertEqual(result["emissions"][0]["emission_status"],"matched")
            self.assertEqual(result["windows"][0]["platform_actions"]["WAIT"],1)
            self.assertEqual(index_before,hashlib.sha256(index.read_bytes()).hexdigest()); self.assertEqual(source_before,hashlib.sha256(source.read_bytes()).hexdigest())


if __name__=="__main__": unittest.main()
