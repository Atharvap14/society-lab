# AI Village: access incidents to reproduce operationally

**The historical record supports several competing access explanations, not a confirmed “document corruption” mechanism.** A useful next experiment must represent document identity, permissions and browser state separately. A generic file-release task does not test these incidents.

Source: `dataset-1ac43f5141de` v1, hash `16849167aecaa4815684f621d12940c905f18fa327e615778dae68362ee4883e`. These are real AI Village logs during the human-subjects experiment task, 8–11 September 2025: 2,000 retained messages, six agent speakers and 17 user posts. The requested fortnight contains 4,637 posts; the earliest 2,000 are retained, so later resolutions are censored. All message audiences are unknown.

The [machine packet](../.runtime/village-access-grounding/grounding-v1.json) contains 38 exact original messages, timestamps, source lines and text SHA256 hashes. Its schema is `village_access_grounding_v1`. The [expanded incident packet](../.runtime/village-access-grounding/incident-packet.json) includes literal URL comparisons, proposed outcomes and falsifiers. These are local source records, not bundled raw data. No model calls or scientific-record changes were needed.

## Five source-grounded episodes

### 1. A permission fix did not establish peer access

On 8 September, o3 reports a 404 for the Power-Calc Sheet and asks for a sharing or canonical-link check: `a1b844bd-df28-4ace-9a35-2614ec9377b5`, 17:47:48 UTC. Opus reports organization-only viewing at 17:50:38 (`73a398fc-ded4-4639-ba42-9fd943ce56d2`), then “anyone with link” viewing at 17:51:25 (`2b9269e7-8b00-4228-89bb-cc80b250bc78`). At 18:05:30, o3 reports the same literal sheet URL still failing **while signed in** (`5a152f0c-d5fc-44d5-a9a4-2ab5009dd5d8`).

The reported ID is `1CgTB5XbqXqT_4_xfR1pcc56DpJYIa7XQw9NJMzH8kNo`. The source does not establish its existence, actual ACL or what URL reached the browser. Permission change, copied reference and peer access must be separate state transitions.

### 2. The backup-document test included an admitted typo

GPT-5 reports creating a backup kickoff document, setting public-link viewing and copying its link. It then says a **manually typed** URL produced a private-window 404, believed to be a typo: `0150b373-d379-4c0a-be9b-d5c63c1fd883`, 8 September 18:34:06. Its later recap repeats this (`4b10a594-4838-468a-b7f3-aa430e251a2e`, 19:19:02).

This is a concrete rival to treating every failure as service corruption. Earlier o3 supplied a kickoff reference containing placeholder `xxxxxxx` and an instruction to replace it (`b150b758-af56-4eb3-99df-bbeb5a8a048a`, 17:58:28). A later duplicate was explicitly still restricted (`eb11bf0e-4500-428e-9f35-4e6fbf592438`, 18:24:43). These are different named artifacts or states; they cannot be merged into one verified public document.

### 3. Version recreation followed an underdetermined failure

Opus posts v4 with ID `1zB3ndzFvgNpxLGekR2YYUh` (`1803b8e5-2fed-4ff1-a1d2-aaf0d9c1e4dd`, 8 September 19:13:21). At 19:34:34 it says it is pressing Enter (`5ce24cb8-fea8-4901-8d12-108a6e1fec70`); at 19:35:46 its summary says it forgot to press Enter before ending the session (`58b62bb0-b438-40d9-9581-ff09a92005b3`). Neither post verifies a completed navigation.

After a reported private-window 404, Opus calls v4 corrupted (`bfaca189-fb89-4b36-b9c7-209bd0282626`, 19:38:28). One minute later it reports the ACL was organization-only (`6c1aada1-7b28-4740-8b22-2eed50fe3877`, 19:39:20), changes it, and still asserts corruption without a reported new test before copying v5. Two v5 reports have different literal IDs: `1WTdhfnCSwNcX-HN8cbvWsV` at 19:42:13 (`6742c8bb-af9c-47b0-85a4-b02667307ab8`) and `1WTdhfnCSwNcX-HN8cbvWsVr` at 19:44:50 (`19ab0db7-9360-4ed9-8c25-412854f56fb9`). We do not know which, if either, was canonical.

On 9 September, Opus reports v6 intact through Drive despite direct-link failures (`75e99312-4f1a-48fd-9667-c5311c994967`, 17:40:01). Sonnet separately reports ethics-document progress through Drive (`cc611ef7-88ef-48c8-ba1c-e5afa454d87a`, 8 September 19:09:22). These weaken a blanket destruction/no-progress interpretation. They remain reports, not inspected files.

### 4. Clipboard and authentication were separate blockers

o3 reports copying collaborator emails instead of a public link (`35a389e1-2f2b-4650-bf54-aecb002507cd`, 9 September 17:38:31). The next day it reports the permission change completed while the correct link-copy and incognito test remain unfinished (`0d7738f7-0de4-4d14-9fa0-04db0070e853`, 17:27:30).

Grok reports an incognito Drive sign-in prompt, no known password and a return to its signed-in window (`716ed4e0-d6f5-49f2-a6fa-78f1beaed9c2`, `f4b594c8-e827-4f3a-b02c-a4ee1788c297`, 10 September 17:13–17:14). Anonymous public viewing, authenticated listing and editing require different authority. An incognito login prompt is not evidence that a document disappeared.

### 5. A corrected form string did not settle the diagnosis

Opus posts two different form URLs at 11 September 18:21:48 (`bd62214e-4dcd-4a61-a426-f147f847e6c6`). An exact text comparison finds a `q`/`o` replacement **and an inserted `s`**; the source's “character difference” should not be silently simplified to one changed character.

At 18:25:52, Opus reports a private-browser PASS but says o3 still gets 404 for the alleged corrected string (`8d3d18d4-23f4-4b4a-8752-5f4af859a187`). o3 later says aggregated FAIL/PASS reports rule out typos and imply owner-only access (`57f32cfc-b933-42d9-854c-a0d4d10c3e49`); this is an inference, not ground truth. GPT-5 starts a backup form in parallel (`e8c23fb4-df87-4c4f-b716-26fed8f8ea0d`). Opus cannot open the **editor** in unsigned private browsing and switches to a normal signed-in window (`02ad6eb0-3c97-4c38-8019-5e5d3c50bb3b`, 18:28:37). Sonnet retains a separate email sign-in dependency. Responder access, editor access and email authority cannot share one success flag.

## One testable causal question

**Does binding access reports to an exact reference and browser principal reduce avoidable document recreation after ambiguous 404s?** The proposed mechanism is mistaken aggregation: reports about different strings, copies or sessions are treated as one artifact's failure, then become a global corruption diagnosis. The logs motivate this question; they do not identify that mechanism historically or establish novelty.

Randomize whole six-agent teams to ordinary bounded free-text reports versus reference-and-session-bound receipts: artifact ID, exact attempted URL hash, endpoint role, effective profile/principal and completed navigation outcome. Both conditions retain the same document truths, tools, permission/session distribution, scheduler and action/message budgets. The receipt must expose only facts available through ordinary tool observations; it must not inject the correct URL or hidden fault.

Primary outcomes are oracle-valid access for required peer roles and redundant recreations while a repair path exists. Independent-task progress and incorrect diagnoses are secondary. No benefit in verified access/recreation despite changed messages weakens the hypothesis. Extra information, action budget, opportunity differences or a different fault distribution would confound the intended comparison. Infrastructure-incomplete teams remain explicitly incomplete; missing task answers in completed teams count as failures.

## Fidelity contract for the next executable world

Represent stable document IDs, content revisions, copied-document genealogy, exact URL parsing, separate viewer/responder/editor permissions, organization/public ACLs, normal and fresh anonymous profiles, clipboard state and a committed Enter/navigation step. Provide both direct URL and authenticated Drive-listing routes, owner and peer observations, a share dialog, independent work and parallel fallback creation. Preserve actual action/send receipts and a hidden deterministic oracle; reset seeded truths and schedules per whole team.

A local operational service and browser/tool adapter can implement this now. Pixel-level HTML/share/Drive pages are a higher-fidelity extension; production Google services, historical cookies, original screenshots/tool returns and original model personalities are not reproduced. Historical URL IDs are evidence only: the new world must use its own controlled namespace. A source-agent label is not a replica of that model. The level is **source-grounded operational simulation**, not historical equivalence or an unrelated arithmetic/file-release pilot.

Only original chat text, source coordinates and goal metadata were checked for this packet. No original screenshot or raw tool-return stream was used to confirm claimed share changes, document state or browser actions. Unknown ground truth must remain unknown when constructing and interpreting the world.
