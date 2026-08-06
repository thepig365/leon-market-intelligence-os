# Leon Frontend Acceptance Guide

Open the protected LMIO dashboard and choose **RC1 验收** in the main menu.

## What to check

1. Confirm the release label says **LMIO v1.0 RC1 — Ready for Operator Acceptance**.
2. Read the six evidence levels. A provider or scheduler must not say verified
   unless a timestamped record exists.
3. Check the readiness blockers and any simulation watermark.
4. Inspect the latest pipeline. A complete run has exactly 21 ordered stages.
5. Use safe controls one at a time. A failed action must preserve old data.
6. Open each of the 13 normal sections and confirm the content is understandable,
   current and not a technical data dump.
7. Repeat on a phone-sized window and check that no content runs off screen.
8. In A–H, choose 批准, 需要修正 or 拒绝, explain why, then save.

## Important meaning

Saving a section decision records Leon's verified identity, release SHA,
section, decision and time. It does not merge code, deploy production, approve
another section or enable trading. The implementing agent cannot approve its
own work.
