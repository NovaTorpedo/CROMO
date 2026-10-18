# CROMO video: YouTube upload text

The film is rendered locally to `video_out/` (git-ignored). **Upload v2:** `CROMO_submission_v2.mp4` (3:30) with
`CROMO_submission_v2.srt` (English captions) and `thumbnail.png` (1280×720). v1 (`CROMO_submission.mp4`, 2:44) is kept
unchanged. See `VIDEO_CREDITS.md` for sources and licences.

## Title (max 100 characters on YouTube)
CROMO: why every factory step exists · Gemma 4 on AMD

## Description (paste everything below, up to "Upload settings")
CROMO reads a factory's own archive with Google's Gemma 4 on the AMD Token Factory, and works out why every process
step exists. Fossil steps have lost their reason and cost money every batch. Fences look pointless but prevent
accidents. CROMO flags the first, protects the second, and warns when a change would break either.

▶ Demo: https://novatorpedo.github.io/CROMO/
▶ Code (MIT): https://github.com/NovaTorpedo/CROMO

Chapters
0:00 A true story
0:32 The problem
0:46 A real case, and why it keeps happening
1:31 CROMO and the Fossil Map
1:46 Ask why: the Why-Trail
2:13 A fence
2:24 Before you change
2:34 Tripwires and safe trials
2:52 Where it runs
3:04 Results
3:16 Find the waste, keep the fences

What you see
- The ALK-04 dig is a replay of the run recorded on the AMD Token Factory (Gemma-4-31B-IT, 16 Oct 2026), labelled
  on screen; a live run takes minutes on the shared endpoint. The other verdicts are stored results of the same AMD run.
- The "Before you change" and Tripwire answers are stored answers computed on AMD.
- The plant, its recipes and its archive are synthetic: a fictional paint company with a hidden answer key.
- Every number comes from the measured result files in the repository (data/recorded).
- The real case at 0:46 is paraphrased from the US Chemical Safety Board's final case study of the 2013 explosion at
  the Williams Olefins Plant in Geismar, Louisiana (csb.gov, 2016); the management-of-change rule is US OSHA
  29 CFR 1910.119(l). The illustration is schematic. CROMO makes no claim about this or any other real incident: it
  helps recover and check the reasons behind a step before it is changed.

Built for the AMD Developer Hackathon ACT III, with Google's Gemma 4 and an Evolus workflow for approvals.
Narration: AssemblyAI Voice Agent API. Music: original, synthesised for this video (CC0). The opening story is
paraphrased from Primo Levi, "The Periodic Table" (1975), chapter "Chromium".

#AMD #Gemma #AI #Manufacturing

## Upload settings
- Visibility: **Unlisted**
- Audience: not made for kids
- Subtitles: English captions are burned into the picture, so don't add the `.srt` on YouTube (with CC on they would
  show twice); keep `CROMO_submission_v2.srt` for any place that asks for a caption file
- Thumbnail: `thumbnail.png`
- Category: Science & Technology
