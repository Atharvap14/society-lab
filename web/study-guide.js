/* Local, unregistered study-choice draft. Retrieval, forms and jobs belong to the host. */
(function (host) {
  'use strict';
  const SOURCE_KINDS = ['dataset', 'discovery', 'selected_audit', 'temporal_audit'];
  const REF_KEYS = ['id', 'version', 'hash'];
  const COMPARISON_KEYS = ['id', 'feature', 'window_id', 'comparison_window_id'];
  const DRAFT_KEYS = ['draft_version', 'available', 'source_refs', 'comparison',
    'research_question', 'matching_behavior_ref', 'registration_status'];
  const NOTE = 'Not registered or attached to protocols; form submission is separate.';
  const STUDIES = [
    {
      id: 'handoff', name: 'Artifact handoff',
      question: 'Would an evidence-check reminder improve a published object?',
      assignment: 'Fresh three-agent teams: baseline, neutral note and evidence-thought note. The coordinator receives its assigned note before its first decision.',
      outcome: 'Code-checked successful publication; incorrect or missing publication scores zero. The first publication ends the run.',
      falsifier: 'Replay the published object against requirements and script a legal inspection/repair route. A confident chat claim alone does not establish object failure.',
      limit: 'Measures executed artifact correctness. It does not measure private verification, trust, later recovery or the historical mechanism. Note content and within-team spillover form a package.'
    },
    {
      id: 'network', name: 'Noisy source diffusion',
      question: 'Does provenance guidance change decisions when reports share a source?',
      assignment: 'Fresh four-agent networks: registered topologies crossed with context. Four reports include a duplicate of one of three independent noisy measurements.',
      outcome: 'Network mean correct binary verdicts; missing verdicts score zero. Source inventories and forwarding lineage are descriptive.',
      falsifier: 'Check which reports share an original source; compare scripted policies that count originals versus report IDs.',
      limit: 'Copy multiplicity is fixed, not randomized. Topology changes degree, routes and opportunity together; the contrast cannot isolate echo amplification or leadership.'
    },
    {
      id: 'complementary', name: 'Complementary evidence',
      question: 'Does communication opportunity help combine distinct private contributions?',
      assignment: 'Fresh four-agent networks: topology crossed with neutral/provenance context. Each starts with its own uniform residue and can send canonical bundles to neighbors.',
      outcome: 'Mean exact submitted modular-total accuracy; missing submissions score zero. All four residues contribute to the oracle.',
      falsifier: 'Exhibit legal all-gather paths and a successful scripted combination. Agreement alone does not establish correct combination.',
      limit: 'Canonical attachment coverage is not knowledge: free text may convey values. Multicast fanout differs across graphs. A topology contrast does not isolate a nominated relay.'
    },
    {
      id: 'resource', name: 'Shared resource',
      question: 'Does a task-specific reminder change legal work during resource closure?',
      assignment: 'Fresh four-agent swarms: reminder versus neutral note before agent-0\'s first decision. Independent work and computer-gated work coexist with an external release and exclusive lease.',
      outcome: 'Whole-swarm completion fraction across eight tasks. Waits, grants, denials and separate task completions are descriptive.',
      falsifier: 'Check explicit dependencies and script independent work while the resource is closed. Waiting text does not establish universal inactivity.',
      limit: 'Exclusivity, costs and release are analogue inventions. Logged waits are not beliefs; not every denial is contention. Independently seeded arms are not paired realized worlds.'
    },
    {
      id: 'timed_resource', name: 'Triggered reminders',
      question: 'Does reminder content help under one registered observed-state trigger?',
      assignment: 'One active and one neutral swarm per seed block, with matched precomputed paths. Register first decision, executed wait with independent work pending, or first observed resource opening.',
      outcome: 'Paired whole-swarm completion difference, including never-delivered units. Seed blocks are uncertainty units.',
      falsifier: 'Replay the trigger on public own-history; include never-eligible, unknown and failed-delivery cases. A note-sensitive fixture only tests insertion plumbing.',
      limit: 'Compares content under one trigger, not different trigger timings. Constructed request receipts do not establish provider consumption. Receipt/wait subgroups change the estimand.'
    },
    {
      id: 'revision_relay', name: 'Correction relay',
      question: 'Does an alternate route change the effect of correction timing?',
      assignment: 'Four fresh two-subject teams per block: early/late correction to B crossed with informative/sham bypass to C. A is scripted; B/C/B/C opportunities and exogenous truth are paired.',
      outcome: 'Exact final C-answer accuracy; correct guesses qualify without attachments. Block contrast D = (late-sham − early-sham) − (late-informative − early-informative).',
      falsifier: 'Test a legal late/no-bypass success and compare assigned cells without filtering on realized forwarding or receipt. All four cells admit successful scripts.',
      limit: 'Assigned timing/route interaction is not relay mediation. Chronology, salience, attribution and repetition remain package differences. No private thought insertion or interaction p-value; intervals require declared assumptions.'
    }
  ];
  const dict = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const keys = (value, expected) => dict(value) && Object.keys(value).sort().join(',') === expected.slice().sort().join(',');
  const textId = value => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/.test(value);
  const refValid = value => keys(value, REF_KEYS) && textId(value.id) && Number.isSafeInteger(value.version) && value.version > 0 && typeof value.hash === 'string' && /^[0-9a-f]{64}$/.test(value.hash);
  const sourcesValid = value => keys(value, SOURCE_KINDS) && SOURCE_KINDS.every(kind => refValid(value[kind]));
  const comparisonValid = value => keys(value, COMPARISON_KEYS) && COMPARISON_KEYS.every(key => textId(value[key])) && value.window_id !== value.comparison_window_id;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const cloneRef = value => ({id: value.id, version: value.version, hash: value.hash});
  const unavailable = reason => ({available: false, reason});
  function originGate(draft) {
    if (!keys(draft, DRAFT_KEYS) || draft.draft_version !== 'study-guide-draft-v1' || draft.available !== true || draft.registration_status !== 'unregistered_local_draft') return unavailable('Unsupported or absent local study draft.');
    if (!sourcesValid(draft.source_refs) || !comparisonValid(draft.comparison)) return unavailable('Exact typed origin references or original comparison are unavailable.');
    if (draft.matching_behavior_ref !== null && !refValid(draft.matching_behavior_ref)) return unavailable('The optional matching behavior declaration is malformed.');
    return {available: true, reason: null};
  }
  function questionGate(question) {
    if (typeof question !== 'string' || !question.trim() || question.trim().length > 4000 || question.length > 4000) return unavailable('Enter a research question of 1–4000 characters. This local text is retained; study navigation is disabled until valid.');
    return {available: true, reason: null};
  }
  function validate(draft) {
    const origin = originGate(draft);
    return origin.available ? questionGate(draft.research_question) : origin;
  }
  function fromEpisode(packet, expected, question) {
    const episode = host.EpisodeWorkspace;
    if (!episode || typeof episode.validate !== 'function' || typeof episode.draft !== 'function') return unavailable('The episode source validators are unavailable.');
    const gate = episode.validate(packet, expected);
    if (gate?.available !== true) return unavailable(typeof gate?.reason === 'string' ? gate.reason : 'The exact episode source gates are unavailable.');
    let questionDraft;
    try { questionDraft = episode.draft(question); }
    catch (_) { return unavailable('Enter a research question of 1–4000 characters.'); }
    const draft = {
      draft_version: 'study-guide-draft-v1', available: true,
      source_refs: Object.fromEntries(SOURCE_KINDS.map(kind => [kind, cloneRef(packet.source_refs[kind])])),
      comparison: Object.fromEntries(COMPARISON_KEYS.map(key => [key, packet.comparison[key]])),
      research_question: questionDraft.research_question,
      matching_behavior_ref: gate.behavior_available === true ? cloneRef(packet.behavior.ref) : null,
      registration_status: 'unregistered_local_draft'
    };
    const checked = validate(draft);
    return checked.available ? draft : checked;
  }
  function originHTML(draft) {
    const refs = SOURCE_KINDS.map(kind => '<tr><td>'+esc(kind.replace(/_/g, ' '))+'</td><td class="mono">'+esc(draft.source_refs[kind].id)+'</td><td>'+draft.source_refs[kind].version+'</td><td class="hash">'+esc(draft.source_refs[kind].hash)+'</td></tr>').join('');
    const behavior = draft.matching_behavior_ref;
    const behaviorText = behavior ? '<p>Optional exact matching behavior declaration: <span class="mono">'+esc(behavior.id)+' · v'+behavior.version+'</span><br><span class="hash">'+esc(behavior.hash)+'</span></p>' : '<p>Matching behavior: Unknown — no exact matching behavior was available and explicitly requested.</p>';
    return '<details class="raw-detail"><summary>Exact origin pins and original comparison</summary><div class="table-wrap"><table><thead><tr><th>SOURCE</th><th>ID</th><th>VERSION</th><th>HASH</th></tr></thead><tbody>'+refs+'</tbody></table></div><p class="mono">'+COMPARISON_KEYS.map(key => esc(key)+' = '+esc(draft.comparison[key])).join('<br>')+'</p>'+behaviorText+'<p class="field-help">Copied local declarations from a validated episode packet. This guide does not reread sources, authenticate later client edits, infer a mechanism or promote a behavior. A pre-existing form behavior/source selection must be reviewed independently; this draft supplies no registered source.</p></details>';
  }
  function unknownHTML(reason) {
    return '<section class="panel study-guide"><div class="panel-heading"><h2>Choose a study</h2></div><div class="panel-body"><p class="soft-text">Unknown — '+esc(typeof reason === 'string' ? reason.slice(0,1000) : 'Unsupported local study draft.')+'</p><div class="note">'+NOTE+'</div></div></section>';
  }
  function questionHTML(draft, gate) {
    const text = typeof draft.research_question === 'string' ? draft.research_question.slice(0,4000) : '';
    const clipped = typeof draft.research_question === 'string' && draft.research_question.length > 4000;
    return '<label class="field full"><span>Editable local research question</span><textarea rows="4" maxlength="4000" data-study-guide-question>'+esc(text)+'</textarea></label>'+(gate.available ? '' : '<p class="field-help">'+esc(gate.reason)+'</p>')+(clipped ? '<p class="field-help">Question display is truncated to 4000 characters; the original invalid local draft has not been replaced.</p>' : '');
  }
  function render(draft) {
    const origin = originGate(draft);
    if (!origin.available) return unknownHTML(origin.reason);
    const gate = questionGate(draft.research_question);
    const choices = STUDIES.map(study => '<section class="detail-section"><h3>'+esc(study.name)+'</h3><p>'+esc(study.question)+'</p><dl class="key-value"><dt>Assignment</dt><dd>'+esc(study.assignment)+'</dd><dt>Executed outcome</dt><dd>'+esc(study.outcome)+'</dd><dt>Cheapest falsifier</dt><dd>'+esc(study.falsifier)+'</dd><dt>Fit and scope limits</dt><dd>'+esc(study.limit)+'</dd></dl><button class="button" type="button" data-study-guide-open="'+study.id+'"'+(gate.available ? '' : ' disabled')+'>Open '+esc(study.name)+' form →</button></section>').join('');
    return '<section class="panel study-guide"><div class="panel-heading"><div><h2>Choose a falsifiable study</h2><p>Six supported designs; no design is selected or judged to fit automatically.</p></div></div><div class="panel-body">'+questionHTML(draft,gate)+'<div class="note">'+NOTE+' Origin is motivation only; fit is unreviewed. The draft has not been sent to subjects. Opening a form launches no study and changes no execution mode.</div><p>Define a rival explanation and what would contradict it. Named references, event records, constructed requests and executed outcomes are distinct measurements. Assignments below are whole-team designs; turns and agents are not extra randomized replicates. A graph contrast or gradient/circulation decomposition is not a behavioral or causal finding.</p>'+originHTML(draft)+choices+'<p class="field-help">A question needing another capability remains unsupported by these designs. Environment authoring and separate protocol registration remain explicit host actions; this guide creates neither.</p></div></section>';
  }
  function context(draft) {
    const origin = originGate(draft);
    if (!origin.available) return unknownHTML(origin.reason);
    const gate = questionGate(draft.research_question);
    const question = typeof draft.research_question === 'string' ? draft.research_question.slice(0,4000) : '';
    const clipped = typeof draft.research_question === 'string' && draft.research_question.length > 4000;
    return '<section class="panel study-guide-context"><div class="panel-heading"><h2>Retained local question</h2></div><div class="panel-body"><p class="message-full">'+(question ? esc(question) : 'Question currently empty.')+'</p>'+(gate.available ? '' : '<p class="field-help">'+esc(gate.reason)+'</p>')+(clipped ? '<p class="field-help">Question display is truncated to 4000 characters; the original invalid local draft has not been replaced.</p>' : '')+'<div class="note">'+NOTE+' Origin is motivation only; fit is unreviewed. The draft has not been sent to subjects.</div>'+originHTML(draft)+'<div class="action-row"><button class="button" type="button" data-study-guide-open="guide">Back to study guide →</button><button class="button" type="button" data-view="episode">Return to Episode →</button><button class="button" type="button" data-study-guide-clear="true">Clear local unregistered draft</button></div></div></section>';
  }
  host.StudyGuide = Object.freeze({fromEpisode, validate, render, context});
})(globalThis);
