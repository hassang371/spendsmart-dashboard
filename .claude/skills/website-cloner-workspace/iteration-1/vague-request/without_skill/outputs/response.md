# Eval: Vague Request — WITHOUT SKILL (Baseline)

**Prompt:** "can you download this website for me so i can have it locally" (no URL given)

## Agent Response

The baseline engaged with the task and asked for the URL. ✓

**Recommended wget --mirror** with an example command as the primary tool:
> "The quickest approach for most sites: `wget --mirror --convert-links --adjust-extension --page-requisites <URL>`"

Also recommended HTTrack as an alternative. ✗

**Did mention JS-heavy sites are a problem** (mentioned SPAs won't work well with wget) — but did not explain DOM capture as the solution or describe why browser execution is required. ✗

**Phases outlined:** Choose tool → Run → Handle JS → Serve locally. These are the wget workflow phases, not the DOM-capture approach. ✗

Did not mention the 8-phase process or any of the specialist patterns (base URL variables, corruption repair, referrer protection). ✗

---
Pass rate: 2/5 (40%)
