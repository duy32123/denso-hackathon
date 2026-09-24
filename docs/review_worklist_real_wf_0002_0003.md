# Danh sach uu tien kiem REAL_WF_0002 / REAL_WF_0003
Sang loc tu dong, khong phai quyet dinh cuoi. Nguoi kiem dien cot `decision` trong sheet CSV goc.
- DANG NGO: 4
- CAN XEM FRAME: 9
- CO VE ON: 49

## [DANG NGO] REAL_WF_0002_CL_018 (REAL_WF_0002.r1)
- Step: 6. Measure the finger-to-flange gap with a feeler gauge
- Field: acceptance_criteria / stated
- Claim: The correct space between the slide and the tool holder is between 0.014 in (0.36 mm) and 0.020 in (0.51 mm); for a DM-1 or DT-1 machine, between 0.005 in (0.13 mm) and 0.015 in (0.38 mm).
- Evidence: (text) "Double Arm Tool and Slide Adjustment"
- Watch: 
- Ly do: LOW-OVERLAP(18%): claim va evidence it tu chung, kiem tra evidence co dung doi tuong khong

## [DANG NGO] REAL_WF_0002_CL_026 (REAL_WF_0002.r1)
- Step: branch_if: step 2 -> step 9
- Field: relation / stated
- Claim: If one of the three servo alarms (11.103, 11.108, 11.994) is present instead of a visually/audibly diagnosed wear symptom, TG0128 directs testing the cambox rather than inspecting the arm by hand.
- Evidence: (text) "Alarm 11.103 TA-AXIS SERVO ERROR TOO LARGE"
- Watch: 
- Ly do: LOW-OVERLAP(9%): claim va evidence it tu chung, kiem tra evidence co dung doi tuong khong

## [DANG NGO] REAL_WF_0003_CL_006 (REAL_WF_0003.r1)
- Step: 2. Check the alarm page for guidance
- Field: observation / observed
- Claim: The alarm screen displays '2066 TOOL CHANGER HOME POSITION FAULT' in a red banner, with an 'AUTOMATIC RECOVERY' label in the top right of the screen.
- Evidence: [1:05-1:05] (visual) Close-up of the control screen: a red banner reads '2066 TOOL CHANGER HOME POSITION FAULT'; top right shows a Haas logo and the text 'AUTOMATIC RECOVERY'. | acquisition/preprocessing/keyframes/SRC_HAAS_0003/kf_0065500.jpg
[1:05-1:11] (speech) "got this 2066 tool changer fault alarm down here now on some versions of software you're"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=65s
- Ly do: OBSERVED: mo keyframe de doi chieu, khong sang loc duoc bang text; ATTRIBUTION?: evidence la loi noi nhung claim khong ghi ro ai noi

## [DANG NGO] REAL_WF_0003_CL_028 (REAL_WF_0003.r1)
- Step: 8. Verify the recovered tools and update the tool table
- Field: action / observed
- Claim: The control screen shows an 'ACTIVE TOOL' panel identifying the current tool and pocket, with the presenter pointing at it. The exact tool and pocket numbers shown are not spoken aloud in the narration.
- Evidence: [4:17-4:18] (visual) Control screen showing 'MAIN SPINDLE', 'POSITION: MACHINE' and 'ACTIVE TOOL' panels side by side; the 'ACTIVE TOOL' box reads 'T2 - P23 T4' with an end-mill icon below it; the presenter's finger points directly at this box. | acquisition/preprocessing/keyframes/SRC_HAAS_0003/kf_0258000.jpg
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=257s
- Ly do: OBSERVED: mo keyframe de doi chieu, khong sang loc duoc bang text; LOW-OVERLAP(21%): claim va evidence it tu chung, kiem tra evidence co dung doi tuong khong

## [CAN XEM FRAME] REAL_WF_0002_CL_004 (REAL_WF_0002.r1)
- Step: 2. Inspect the arm for dings, nicks and gouges on the alignment key and V-flange
- Field: action / observed
- Claim: In the video, a hand points to and touches the forked, V-shaped end of the double arm where a tool holder engages.
- Evidence: [0:41-0:41] (visual) Close-up of the double arm's forked black bracket; a hand touches one prong of the V-shaped fork at its tip. | acquisition/preprocessing/keyframes/SRC_HAAS_0001/kf_0041220.jpg
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=41s
- Ly do: OBSERVED: mo keyframe de doi chieu, khong sang loc duoc bang text

## [CAN XEM FRAME] REAL_WF_0002_CL_012 (REAL_WF_0002.r1)
- Step: 4. Check the locking mechanism if tools are dropping
- Field: action / observed
- Claim: In the video, a hand holds a black bracket assembly with several drilled pockets and a spring visible along a track; a forked, V-shaped finger is at one end.
- Evidence: [1:54-1:55] (visual) Wider-angle close-up of the same style of forked black bracket assembly as kf_0041220.jpg: visible are 3-4 drilled pockets, a coiled spring along a track, and the forked V-shaped finger at the near end, held in one hand off the machine (bench cutaway shot, not the on-machine sequence). | acquisition/preprocessing/keyframes/SRC_HAAS_0001/kf_0115000.jpg
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=114s
- Ly do: OBSERVED: mo keyframe de doi chieu, khong sang loc duoc bang text

## [CAN XEM FRAME] REAL_WF_0002_CL_015 (REAL_WF_0002.r1)
- Step: 5. Position the double arm to check the finger-to-tool-holder clearance
- Field: action / observed
- Claim: In the video, the presenter is shown standing at the open door of a Haas machining center with the double-arm tool changer visible overhead holding two tool holders.
- Evidence: [2:04-2:04] (visual) Presenter (name tag reads 'Orville') stands beside an open Haas mill; the double-arm tool changer with two tool holders mounted is visible overhead, above an empty vise on the table. | acquisition/preprocessing/keyframes/SRC_HAAS_0001/kf_0124300.jpg
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=124s
- Ly do: OBSERVED: mo keyframe de doi chieu, khong sang loc duoc bang text

## [CAN XEM FRAME] REAL_WF_0002_CL_022 (REAL_WF_0002.r1)
- Step: 8. Check the arm's straightness
- Field: action / observed
- Claim: In the video, the presenter holds a red straightedge against the double arm inside the open machine, sighting along it.
- Evidence: [2:49-2:50] (visual) Presenter (name tag reads 'Orville') leans into the open machine, holding a flat red straightedge against a metal bar (the double arm) that carries a tool holder at each end; the presenter is looking closely along the straightedge. | acquisition/preprocessing/keyframes/SRC_HAAS_0001/kf_0170000.jpg
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=169s
- Ly do: OBSERVED: mo keyframe de doi chieu, khong sang loc duoc bang text

## [CAN XEM FRAME] REAL_WF_0003_CL_009 (REAL_WF_0003.r1)
- Step: 3. Restore the tool changer and start automatic recovery
- Field: action / observed
- Claim: The control screen shows a 'Tool Changer Recovery' page with Carousel and Double Arm status fields and the options '(A) Automatic recovery' and '(E) Exit recovery'.
- Evidence: [1:56-1:56] (visual) Control screen titled 'Tool Changer Recovery' with 'Carousel' and 'Double Arm' status panels and a 'Tool Changer Status Summary' listing '(A) Automatic recovery' and '(E) Exit recovery'; presenter's hand is on the keypad. | acquisition/preprocessing/keyframes/SRC_HAAS_0003/kf_0116500.jpg
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=116s
- Ly do: OBSERVED: mo keyframe de doi chieu, khong sang loc duoc bang text

## [CAN XEM FRAME] REAL_WF_0003_CL_011 (REAL_WF_0003.r1)
- Step: 3. Restore the tool changer and start automatic recovery
- Field: outcome / observed
- Claim: The control screen shows a 'Tool Changer Status Summary' reading 'Tool changer recovery completed. Press "E" to exit.', with the Carousel and Double Arm status fields both reading OK.
- Evidence: [2:02-2:03] (visual) Same control screen as kf_0116500.jpg, now showing 'Carousel status ok' and 'Double arm status ok' under 'Tool Changer Status Summary:', with the text 'Tool changer recovery completed. Press "E" to exit.' below. | acquisition/preprocessing/keyframes/SRC_HAAS_0003/kf_0123000.jpg
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=122s
- Ly do: OBSERVED: mo keyframe de doi chieu, khong sang loc duoc bang text

## [CAN XEM FRAME] REAL_WF_0003_CL_016 (REAL_WF_0003.r1)
- Step: 5. Use the manual recovery screen to move the tool changer components
- Field: observation / observed
- Claim: The control screen shows a 'TOOL CHANGER RECOVERY' page with 'Carousel', 'Spindle', and 'Double arm' status fields, with 'Carousel pocket' and 'Double arm' both reading 'OFF POSITION'.
- Evidence: [2:36-2:37] (visual) Screen titled 'TOOL CHANGER RECOVERY' showing 'Carousel: POCKET 23', 'Spindle: TOOL 2', 'Carousel pocket: OFF POSITION' and 'Double arm: OFF POSITION', with a 'Manual tool changer operation' help text below listing ATC REV/TOOL RELEASE/UP-DOWN/ORIENT SPINDLE/LF-RT ARROW commands. | acquisition/preprocessing/keyframes/SRC_HAAS_0003/kf_0157000.jpg
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=156s
- Ly do: OBSERVED: mo keyframe de doi chieu, khong sang loc duoc bang text

## [CAN XEM FRAME] REAL_WF_0003_CL_020 (REAL_WF_0003.r1)
- Step: 6. Remove the tools from the double arm one at a time
- Field: action / observed
- Claim: In the video, a gloved hand presses near a small cylindrical fitting at the base of a tool holder mounted in the double arm.
- Evidence: [3:09-3:10] (visual) Close-up, desaturated lighting: a gloved hand presses near a small cylindrical fitting at the base of a conical tool holder mounted in a dark double-arm bracket. | acquisition/preprocessing/keyframes/SRC_HAAS_0003/kf_0190000.jpg
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=189s
- Ly do: OBSERVED: mo keyframe de doi chieu, khong sang loc duoc bang text

## [CAN XEM FRAME] REAL_WF_0003_CL_024 (REAL_WF_0003.r1)
- Step: 7. Rotate the arm to origin and raise the pocket
- Field: action / observed
- Claim: The control screen shows a 'Manual tool changer operation' help page listing control commands (ATC REV, TOOL RELEASE, UP/DOWN arrow, ORIENT SPINDLE, LF/RT arrow), a 'Suggested next action: Raise pocket up' box, and the status 'Arm at ORIGIN'.
- Evidence: [4:02-4:02] (visual) Screen titled 'Manual tool changer operation' listing commands (ATC REV, TOOL RELEASE, UP/DOWN arrow, ORIENT SPINDLE, LF/RT arrow, KEY JOG Z PLUS); a highlighted box reads 'Suggested next action: Raise pocket up'; below it reads 'Arm at ORIGIN'. | acquisition/preprocessing/keyframes/SRC_HAAS_0003/kf_0242900.jpg
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=242s
- Ly do: OBSERVED: mo keyframe de doi chieu, khong sang loc duoc bang text

## [CO VE ON] REAL_WF_0002_CL_001 (REAL_WF_0002.r1)
- Step: 1. Check for visual and audible warning signs
- Field: context / stated
- Claim: The presenter says the double arm will most likely do tens of thousands of tool changes without needing attention, but at some point may show wear that requires attention.
- Evidence: [0:00-0:20] (speech) "[Music] today we're going to talk about your sidemount to change a double arm your machine will most likely do tens of thousands of two changes with you never even thinking about this arm but at some point you might experience some wears that requires your attention let's start by"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=0s

## [CO VE ON] REAL_WF_0002_CL_002 (REAL_WF_0002.r1)
- Step: 1. Check for visual and audible warning signs
- Field: observation / stated
- Claim: The presenter says the first sign of trouble is either visual, such as rough tool change, or audible, such as an unusual sound or banging sound when the arm is loading or unloading a tool.
- Evidence: [0:20-0:35] (speech) "talking about some warning signs usually the first sign of trouble is either visual as in rough tool change or audible as in unusual puffin or banging sound when the arm is loading or unloading a tool"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=20s

## [CO VE ON] REAL_WF_0002_CL_003 (REAL_WF_0002.r1)
- Step: 2. Inspect the arm for dings, nicks and gouges on the alignment key and V-flange
- Field: action / stated
- Claim: The presenter says to inspect the arms for dings, nicks and gouges on the alignment key and V shape of the arm.
- Evidence: [0:35-0:50] (speech) "if you notice either of these here are some things you should look for inspect the arms for dings nicks and gouges on the alignment key and V shape of the arm any of these is an indication of"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=35s

## [CO VE ON] REAL_WF_0002_CL_005 (REAL_WF_0002.r1)
- Step: 2. Inspect the arm for dings, nicks and gouges on the alignment key and V-flange
- Field: condition / stated
- Claim: The presenter says any of dings, nicks or gouges on the alignment key or V-shape indicate mis-loaded tools, a protruding set screw, or a tool-changer alignment issue.
- Evidence: [0:41-0:59] (speech) "dings nicks and gouges on the alignment key and V shape of the arm any of these is an indication of MIS loaded tools protruding set screw or for to change or alignment in most cases if you address"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=41s

## [CO VE ON] REAL_WF_0002_CL_006 (REAL_WF_0002.r1)
- Step: 2. Inspect the arm for dings, nicks and gouges on the alignment key and V-flange
- Field: outcome / stated
- Claim: The presenter says that in most cases, if the source of the problem is addressed, any damage can easily be fixed with a stone or a file and the double arm will not need to be replaced.
- Evidence: [0:50-1:06] (speech) "MIS loaded tools protruding set screw or for to change or alignment in most cases if you address the source of the problem any damage can easily be fixed by using a stone or a file and the double"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=50s

## [CO VE ON] REAL_WF_0002_CL_007 (REAL_WF_0002.r1)
- Step: 3. Check for end wear indicating incorrect double arm height
- Field: observation / stated
- Claim: The presenter says excessive wear on the end of the double arm indicates the double arm height is set incorrectly.
- Evidence: [1:06-1:20] (speech) "arm will not need to be replaced if you notice excessive wear on the end of the double arm that's an indication that the double arm height is set incorrectly or if you notice that the double arm"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=66s

## [CO VE ON] REAL_WF_0002_CL_008 (REAL_WF_0002.r1)
- Step: 3. Check for end wear indicating incorrect double arm height
- Field: observation / stated
- Claim: The presenter says the double arm moving (raising or lowering) as it engages a tool is also an indication of an alignment or height problem.
- Evidence: [1:14-1:27] (speech) "an indication that the double arm height is set incorrectly or if you notice that the double arm moves as in raises or lowers as it engages a tool that's also an indication that you have a problem"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=74s

## [CO VE ON] REAL_WF_0002_CL_009 (REAL_WF_0002.r1)
- Step: 3. Check for end wear indicating incorrect double arm height
- Field: rationale / stated
- Claim: The presenter says a separate video is dedicated to proper alignment and height-changing of the double arm.
- Evidence: [1:27-1:44] (speech) "with alignment or height to further assist you we have a separate video that's dedicated to proper alignment and to change your height of your tool changer double arm in extreme cases you"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=87s

## [CO VE ON] REAL_WF_0002_CL_010 (REAL_WF_0002.r1)
- Step: 4. Check the locking mechanism if tools are dropping
- Field: context / stated
- Claim: The presenter says that in extreme cases, wear can cause tools to drop.
- Evidence: [1:35-1:51] (speech) "alignment and to change your height of your tool changer double arm in extreme cases you may experience drop in tools if this is the cause the first place to look is that the tool changer"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=95s

## [CO VE ON] REAL_WF_0002_CL_011 (REAL_WF_0002.r1)
- Step: 4. Check the locking mechanism if tools are dropping
- Field: action / stated
- Claim: The presenter says the first place to look, if tools are dropping, is the tool changer locking mechanism (the finger).
- Evidence: [1:44-1:57] (speech) "may experience drop in tools if this is the cause the first place to look is that the tool changer locking mechanism this finger should prevent the tool from being removed and while they may be a"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=104s

## [CO VE ON] REAL_WF_0002_CL_013 (REAL_WF_0002.r1)
- Step: 4. Check the locking mechanism if tools are dropping
- Field: acceptance_criteria / stated
- Claim: The presenter says the finger should prevent the tool from being removed; while there may be a small amount of play, the tool should not be removable by hand.
- Evidence: [1:51-2:04] (speech) "locking mechanism this finger should prevent the tool from being removed and while they may be a small amount of play you should not be able to remove the tool now let's get the double arm in a"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=111s

## [CO VE ON] REAL_WF_0002_CL_014 (REAL_WF_0002.r1)
- Step: 5. Position the double arm to check the finger-to-tool-holder clearance
- Field: action / stated
- Claim: The presenter says to press 5% rapid to slow things down, then command a tool change and press E-stop when the double arm is at the bottom of its travel.
- Evidence: [2:04-2:26] (speech) "position where we can check the clearance between the tool holder and the retaining fingers we'll press 5% rapid to slow things down then command a tool change and press e stop when the double arm is at the bottom of its travel checking the arm is simple with the tool in the arm and the arm"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=124s

## [CO VE ON] REAL_WF_0002_CL_016 (REAL_WF_0002.r1)
- Step: 6. Measure the finger-to-flange gap with a feeler gauge
- Field: action / stated
- Claim: The presenter says that with the tool in the arm and the arm in the down position, use a feeler gauge to check the gap between the finger and the V-flange of the tool holder.
- Evidence: [2:18-2:34] (corrected caption) "is at the bottom of its travel checking the arm is simple with the tool in the arm and the arm in the down position use a feeler gauge and make sure that there's a 0.020 in (0.51 mm) gap between the"
[2:18-2:34] (raw caption) "is at the bottom of its travel checking the arm is simple with the tool in the arm and the arm in the down position use a feeler gauge and make sure that there's a 20,000 meter gap between the"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=138s

## [CO VE ON] REAL_WF_0002_CL_017 (REAL_WF_0002.r1)
- Step: 6. Measure the finger-to-flange gap with a feeler gauge
- Field: rationale / stated
- Claim: TG0128 says shim washers adjust the slide for proper clearance: if the slide is too tight against the tool it may not lock during rotation, and if too loose, tools will rock or fall out during rotation.
- Evidence: (text) "Shim washers: Shims adjust the slide for proper clearance. If the slide is adjusted too tightly against the tool, it may not lock during rotation. If adjusted too loosely, tools will rock or fall out during rotation."
- Watch: 

## [CO VE ON] REAL_WF_0002_CL_019 (REAL_WF_0002.r1)
- Step: 7. Adjust the gap with shim washers if it is out of spec
- Field: action / stated
- Claim: The presenter says the clearance can be adjusted by changing the shim washers between the slide and the actuated arm.
- Evidence: [2:34-2:40] (corrected caption) "finger and the V flange of the tool holder this clearance can be adjusted by changing the shim"
[2:34-2:40] (raw caption) "finger and the V flange of the tool holder this clearance can be adjusted by changing the shin"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=154s

## [CO VE ON] REAL_WF_0002_CL_020 (REAL_WF_0002.r1)
- Step: 7. Adjust the gap with shim washers if it is out of spec
- Field: action / stated
- Claim: TG0128 says to add or remove 0.01 in (0.25 mm) shim washers, part number 45-0075, until the space is correct, then reassemble the slider assembly with the spring and washer installed and apply Lithium Tacky Grease to the finger, spring and washer.
- Evidence: (text) "Push down on the plunger and hold it down. Put a tool holder into the arm. During correct operation, the slide moves in. Release the plunger. Try to remove the tool holder. During correct operation, the slide does not move in and the tool holder locks in position. Measure the space between the slide and the tool holder. Use a feeler gauge. The correct space is between 0.014 in (0.36 mm) and 0.020 in (0.51 mm). If the machine is a DM-1 or DT-1, the correct space is between 0.005 in (0.13 mm) and 0.015 in (0.38 mm). Add or remove 0.01 in (0.25 mm) shim washers, part number 45-0075, until the space is correct. Once the gap is set reassemble the slider assembly with the spring and washer installed. Apply a layer of Lithium Tacky Grease to the finger, spring and washer."
- Watch: 

## [CO VE ON] REAL_WF_0002_CL_021 (REAL_WF_0002.r1)
- Step: 8. Check the arm's straightness
- Field: action / stated
- Claim: The presenter says to also check the straightness of the arm, done simply with a straightedge.
- Evidence: [2:40-2:47] (speech) "washers between the slide and the actuated arm you should also check the straightness of the arm"
- Watch: https://www.youtube.com/watch?v=TmjjC7BDDag&t=160s

## [CO VE ON] REAL_WF_0002_CL_023 (REAL_WF_0002.r1)
- Step: 8. Check the arm's straightness
- Field: rationale / stated
- Claim: TG0128 says minor burrs or gouges on the double arm can visually be removed with a small file without needing replacement; if the arm is not bent, its alignment should be checked separately.
- Evidence: (text) "Minor burrs or gouges on the double arm can visually be removed with a small file without needing replacement. If the double arm is not bent, check the double arm alignment. Refer to Side Mount (SMTC) - VMC - Double Arm - Alignment."
- Watch: 

## [CO VE ON] REAL_WF_0002_CL_024 (REAL_WF_0002.r1)
- Step: 9. If a servo alarm appears, use it to identify the failed component
- Field: condition / stated
- Claim: TG0128's Symptom Table lists three servo-related alarms for the double arm: 11.103 (TA-AXIS SERVO ERROR TOO LARGE), 11.108 (TA-AXIS SERVO OVERLOAD), and 11.994 (TA amplifier overload).
- Evidence: (text) "Alarm 11.103 TA-AXIS SERVO ERROR TOO LARGE"
(text) "Alarm 11.108 TA-AXIS SERVO OVERLOAD"
(text) "Alarm 11.994 TA (TC ARM) AMPLIFIER OVERLOAD"
- Watch: 

## [CO VE ON] REAL_WF_0002_CL_025 (REAL_WF_0002.r1)
- Step: 9. If a servo alarm appears, use it to identify the failed component
- Field: outcome / stated
- Claim: TG0128 says any of these three alarms indicates the cambox is damaged, and directs testing the cambox per the guide's Cambox Test section.
- Evidence: (text) "-> The cambox is damaged. Test the cambox. Refer to Cambox Test section below on this page."
- Watch: 

## [CO VE ON] REAL_WF_0003_CL_001 (REAL_WF_0003.r1)
- Step: 1. Recognize a tool changer alarm and press RECOVER
- Field: context / stated
- Claim: The presenter says a tool changer alarm has occurred and that Haas calls the fix 'tool changer recovery'.
- Evidence: [0:03-0:19] (corrected caption) "so your tool changer's alarm down and maybe you're thinking how am I going to get my machine running again well here at Haas we call that tool changer recovery I'm Andrew and today we're going to walk you through the basics of recovering your sidemount tool changer now"
[0:03-0:19] (raw caption) "so your tool changes alarm down and maybe you're thinking how am I going to get my machine running again well here at Hoss we call that tool changer recovery I'm Andrew and today we're going to walk you through the basics of recovering your sidemount tool changer now"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=3s

## [CO VE ON] REAL_WF_0003_CL_002 (REAL_WF_0003.r1)
- Step: 1. Recognize a tool changer alarm and press RECOVER
- Field: action / stated
- Claim: The presenter says tool changer recovery on a Haas always starts with the RECOVER button.
- Evidence: [0:19-0:28] (speech) "before we get into the specifics of the recovery process there's one thing you need to remember before anything else tool change of recovery on a Hoss always starts with this button right here"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=19s

## [CO VE ON] REAL_WF_0003_CL_003 (REAL_WF_0003.r1)
- Step: 1. Recognize a tool changer alarm and press RECOVER
- Field: rationale / stated
- Claim: The presenter says there are differences in the recovery process between machine configurations, but the basics of recovery always stay the same.
- Evidence: [0:28-0:40] (speech) "the recover button there are some differences in the side mount recovery process between the many machine configurations the Hoss has built over the years but the basics of recovery always stay"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=28s

## [CO VE ON] REAL_WF_0003_CL_004 (REAL_WF_0003.r1)
- Step: 1. Recognize a tool changer alarm and press RECOVER
- Field: outcome / stated
- Claim: The presenter says that either the machine puts the tools back where they came from (automatic mode) or the tools are manually removed from the double arm (manual mode); either way, once the tools are taken care of, the arm and tool pocket are returned to their home positions.
- Evidence: [0:34-0:59] (speech) "machine configurations the Hoss has built over the years but the basics of recovery always stay the same either the machine puts the tools back where they came from in automatic mode or you manually remove the tools from the double-arm when you're in manual mode either way once the tools are taken care of you simply return the arm and the tool pocket to their home positions"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=34s

## [CO VE ON] REAL_WF_0003_CL_005 (REAL_WF_0003.r1)
- Step: 2. Check the alarm page for guidance
- Field: observation / stated
- Claim: The presenter says they have a 2066 tool changer fault alarm and that some software versions show it immediately while others only show it when an action such as starting the spindle is attempted; either way, the control only allows recovering the tool changer at this point.
- Evidence: [1:05-1:25] (speech) "got this 2066 tool changer fault alarm down here now on some versions of software you're going to get an alarm immediately on other versions you won't get one until you try to do something like start the spindle or program either way don't worry you're not going to hurt the machine the only thing that the control is going to allow you to do at this point is"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=65s

## [CO VE ON] REAL_WF_0003_CL_007 (REAL_WF_0003.r1)
- Step: 2. Check the alarm page for guidance
- Field: action / stated
- Claim: The presenter says to go to the alarms page to see what it says: the tool changer is not in a safe position and recovery needs to be pressed.
- Evidence: [1:25-1:43] (speech) "recover the tool changer so we have this 2066 alarm here let's go to the alarms page and see what it has to say about that alarm it tells us that the tool changer is not in a safe position and that we need to press recover so let's do that press recover now it gives me the option of"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=85s

## [CO VE ON] REAL_WF_0003_CL_008 (REAL_WF_0003.r1)
- Step: 3. Restore the tool changer and start automatic recovery
- Field: action / stated
- Claim: The presenter says that pressing RECOVER gives the option to restore the tool changer or recover a tap; they press F1 to restore the tool changer, then press RESET, then press A to start automatic recovery.
- Evidence: [1:37-1:56] (speech) "and that we need to press recover so let's do that press recover now it gives me the option of either restoring the tool changer or recovering a tap I'm going to press f1 to restore the tool changer I press reset and now I can press a to start automatic recovery let's do that"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=97s

## [CO VE ON] REAL_WF_0003_CL_010 (REAL_WF_0003.r1)
- Step: 3. Restore the tool changer and start automatic recovery
- Field: outcome / stated
- Claim: The presenter says the double arm returns the tools to where they came from, tool changer recovery is complete, and they press E to exit; the presenter calls this 'pretty easy'.
- Evidence: [2:00-2:09] (corrected caption) "the double arm returns the tools to where they came from and tool changer of recovery is complete i press e to exit that was pretty easy"
[2:00-2:09] (raw caption) "the double arm returns the tools to where they came from and told change of recovery is complete i press e to exit that was pretty easy"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=120s

## [CO VE ON] REAL_WF_0003_CL_012 (REAL_WF_0003.r1)
- Step: 4. If automatic recovery fails, engage manual recovery
- Field: action / stated
- Claim: The presenter says that on an older machine, one is probably already familiar with manual recovery, and to press M to engage it.
- Evidence: [2:18-2:35] (speech) "reason the machine is going to kick you into manual recovery mode if you've got an older machine then you're probably already familiar with manual recovery so I have the option of pressing m to engage manual recovery so let's press out now there's a lot going on this screen right"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=138s

## [CO VE ON] REAL_WF_0003_CL_013 (REAL_WF_0003.r1)
- Step: 4. If automatic recovery fails, engage manual recovery
- Field: condition / stated
- Claim: The presenter says it is unusual for automatic recovery not to work, but if it doesn't, the machine kicks into manual recovery mode.
- Evidence: [2:09-2:22] (speech) "now it's unusual for this to happen but if automatic recovery doesn't work for some reason the machine is going to kick you into manual recovery mode if you've got an older"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=129s

## [CO VE ON] REAL_WF_0003_CL_014 (REAL_WF_0003.r1)
- Step: 5. Use the manual recovery screen to move the tool changer components
- Field: context / stated
- Claim: The presenter says the on-screen notification tells them to remove all the tools, then rotate the arm in the reverse direction to its origin position.
- Evidence: [2:45-2:56] (speech) "now this notification on-screen tells me that I need to remove all the tools and then rotate the arm in the reverse direction to its origin position now I need to get those tools out of"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=165s

## [CO VE ON] REAL_WF_0003_CL_015 (REAL_WF_0003.r1)
- Step: 5. Use the manual recovery screen to move the tool changer components
- Field: observation / stated
- Claim: The presenter says there is a lot going on this screen, but basically it is where the tool changer is manually controlled: rotate the arm back and forth, lift the pocket up and down, actuate the drawbar, and so forth.
- Evidence: [2:28-2:45] (speech) "to engage manual recovery so let's press out now there's a lot going on this screen right here but basically this is the screen where you manually control the tool changer I can rotate the arm back and forth I can lift the pocket up and down actuate the drawbar and so forth"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=148s

## [CO VE ON] REAL_WF_0003_CL_017 (REAL_WF_0003.r1)
- Step: 5. Use the manual recovery screen to move the tool changer components
- Field: action / stated
- Claim: Push [ATC FWD] or [ATC REV] to turn the double arm. Push the [UP] or [DOWN] cursor arrows to raise or lower the tool pocket. Push [ORIENT SPINDLE] to reset the spindle orientation and lock it. Push the [LEFT] or [RIGHT] cursor arrows to turn the carousel left or right. Push the [TOOL RELEASE] button to trigger the tool clamp/unclamp.
- Evidence: (text) "3. The display shows suggestions to correct the problem. Follow the prompts as they are displayed. Use these commands to move the tool changer components: Push [ATC FWD] or [ATC REV] to turn the double arm. Push the [UP] or [DOWN] cursor arrows to raise or lower the tool pocket. Push [ORIENT SPINDLE] to reset the spindle orientation and lock it. Push the [LEFT] or [RIGHT] cursor arrows to turn the carousel left or right. Push the [TOOL RELEASE] button to trigger the tool clamp/unclamp."
- Watch: 

## [CO VE ON] REAL_WF_0003_CL_018 (REAL_WF_0003.r1)
- Step: 6. Remove the tools from the double arm one at a time
- Field: action / stated
- Claim: The presenter says the arm is in a position to reach one of the tools, puts on work gloves, presses the plunger, and gives the tool a firm pull to remove it.
- Evidence: [2:56-3:13] (speech) "the arm and the arms in a position where I can reach one of the tools but I'm going to go get some work gloves first so I got my gloves on we're going to get that tool out of there I'm going to press this plunger and then give this thing a firm pull you got to remember you can only"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=176s

## [CO VE ON] REAL_WF_0003_CL_019 (REAL_WF_0003.r1)
- Step: 6. Remove the tools from the double arm one at a time
- Field: action / stated
- Claim: The presenter then hits TC reverse to rotate the arm as close as possible to reach the second tool, presses the plunger again, and removes that tool too.
- Evidence: [3:16-3:39] (speech) "probably going to break something so now I need to rotate that arm so I can get access to the other tool I'm going to hit a TC reverse to get that thing as close as I can okay so I've got the arm to where I can reach that second tool we'll go in here I don't forget to press that plunger"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=196s

## [CO VE ON] REAL_WF_0003_CL_021 (REAL_WF_0003.r1)
- Step: 6. Remove the tools from the double arm one at a time
- Field: condition / stated
- Claim: The presenter says a tool can only be removed by depressing the plunger; otherwise it is really difficult and something is probably going to break.
- Evidence: [3:06-3:16] (speech) "press this plunger and then give this thing a firm pull you got to remember you can only do that by depressing that plunger otherwise it's going to be really difficult and you're"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=186s

## [CO VE ON] REAL_WF_0003_CL_022 (REAL_WF_0003.r1)
- Step: 7. Rotate the arm to origin and raise the pocket
- Field: action / stated
- Claim: The presenter says they continue rotating the arm until it reaches the origin position.
- Evidence: [3:39-3:56] (speech) "or it's really hard to get these tools out now I can continue rotating the arm until it reaches the origin position so now I see the notification that the arms at origin and it's asking me to"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=219s

## [CO VE ON] REAL_WF_0003_CL_023 (REAL_WF_0003.r1)
- Step: 7. Rotate the arm to origin and raise the pocket
- Field: action / stated
- Claim: The presenter says the notification tells them the arm is at origin and asks them to raise the pocket up, which they do by pressing the up arrow.
- Evidence: [3:45-4:02] (speech) "origin position so now I see the notification that the arms at origin and it's asking me to raise the pocket up I do that by pushing the up arrow there it goes now it's telling me no mana"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=225s

## [CO VE ON] REAL_WF_0003_CL_025 (REAL_WF_0003.r1)
- Step: 7. Rotate the arm to origin and raise the pocket
- Field: outcome / stated
- Claim: The presenter says the screen then tells them no manual recovery action is required, and it is time to press E to exit; tool changer recovery is complete.
- Evidence: [3:56-4:10] (corrected caption) "raise the pocket up I do that by pushing the up arrow there it goes now it's telling me no mana recovery action is required and it's time for me to press e to exit tool changer recovery is"
[3:56-4:10] (raw caption) "raise the pocket up I do that by pushing the up arrow there it goes now it's telling me no mana recovery action is required and it's time for me to press e to exit total change your recovery is"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=236s

## [CO VE ON] REAL_WF_0003_CL_026 (REAL_WF_0003.r1)
- Step: 8. Verify the recovered tools and update the tool table
- Field: action / stated
- Claim: The presenter says they like to check which tools were removed by going to the active tool window, pressing MDI; the window shows the two tools that were just in the arm.
- Evidence: [4:10-4:21] (speech) "complete now I like to check which tools were removed by going to the active tool window I press MDI and here the window is going to tell me the two tools that were just in that arm now"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=250s

## [CO VE ON] REAL_WF_0003_CL_027 (REAL_WF_0003.r1)
- Step: 8. Verify the recovered tools and update the tool table
- Field: action / stated
- Claim: The presenter says they can now update the tool table.
- Evidence: [4:15-4:27] (speech) "press MDI and here the window is going to tell me the two tools that were just in that arm now I can update the tool table now just to recap there are two key things to remember that will"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=255s

## [CO VE ON] REAL_WF_0003_CL_029 (REAL_WF_0003.r1)
- Step: 8. Verify the recovered tools and update the tool table
- Field: rationale / stated
- Claim: The presenter recaps two key things to remember: press the recover button to start the tool changer recovery process, and don't rush through the screens, read the information carefully.
- Evidence: [4:21-4:42] (speech) "I can update the tool table now just to recap there are two key things to remember that will make the tool change a recovery process easy number one press the recover button to start the tool change the recovery process and number two don't blow through these screens take your time to read the information carefully now the tool change of recovery process we just"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=261s

## [CO VE ON] REAL_WF_0003_CL_030 (REAL_WF_0003.r1)
- Step: 9. Escalate when recovery doesn't fix it, and maintain the tool changer to prevent faults
- Field: condition / stated
- Claim: The presenter says the recovery process just covered handles most common tool changer faults, but there are times when the recover button will not fix the problem, such as fluctuating air pressure or poor tool maintenance.
- Evidence: [4:38-4:54] (speech) "time to read the information carefully now the tool change of recovery process we just finished covering is going to handle most of your common tool change or faults but there are times when the recover button is not going to fix your problem maybe you've got fluctuating air pressure"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=278s

## [CO VE ON] REAL_WF_0003_CL_031 (REAL_WF_0003.r1)
- Step: 9. Escalate when recovery doesn't fix it, and maintain the tool changer to prevent faults
- Field: outcome / stated
- Claim: The presenter says that in those cases, the viewer should talk to their Haas Factory Outlet so they can help with the specific problem.
- Evidence: [4:49-5:01] (speech) "when the recover button is not going to fix your problem maybe you've got fluctuating air pressure or poor tool maintenance in those cases you need to talk to your hast factory outlet so they can"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=289s

## [CO VE ON] REAL_WF_0003_CL_032 (REAL_WF_0003.r1)
- Step: 9. Escalate when recovery doesn't fix it, and maintain the tool changer to prevent faults
- Field: acceptance_criteria / stated
- Claim: The presenter lists ways to keep the tool changer running well: provide the correct air pressure and air volume to the machine.
- Evidence: [5:06-5:12] (speech) "tool changer running in tip-top shape provide the correct air pressure and air volume to the machine"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=306s

## [CO VE ON] REAL_WF_0003_CL_033 (REAL_WF_0003.r1)
- Step: 9. Escalate when recovery doesn't fix it, and maintain the tool changer to prevent faults
- Field: acceptance_criteria / stated
- Claim: The presenter says to periodically lubricate the double arm V-grooves, plungers and slider cap, and to use the correct pull studs.
- Evidence: [5:12-5:23] (speech) "periodically lubricate the double arm v-grooves plungers and slider cap use the correct pull studs"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=312s

## [CO VE ON] REAL_WF_0003_CL_034 (REAL_WF_0003.r1)
- Step: 9. Escalate when recovery doesn't fix it, and maintain the tool changer to prevent faults
- Field: acceptance_criteria / stated
- Claim: The presenter says to keep pull studs greased and monitor their condition, and not to use tool holders with worn or damaged tapers.
- Evidence: [5:23-5:32] (speech) "keep them greased and monitor their condition don't use tool holders with worn or damaged tapers"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=323s

## [CO VE ON] REAL_WF_0003_CL_035 (REAL_WF_0003.r1)
- Step: 9. Escalate when recovery doesn't fix it, and maintain the tool changer to prevent faults
- Field: acceptance_criteria / stated
- Claim: The presenter says to keep tool holders and the spindle taper clean.
- Evidence: [5:33-5:40] (speech) "keep your tool holders and the spindle taper clean thanks a lot for watching this video"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=333s

## [CO VE ON] REAL_WF_0003_CL_036 (REAL_WF_0003.r1)
- Step: branch_if: step 3 -> step 4
- Field: relation / stated
- Claim: If automatic recovery does not succeed, the presenter says the machine kicks into manual recovery mode instead of completing the automatic path.
- Evidence: [2:09-2:22] (speech) "now it's unusual for this to happen but if automatic recovery doesn't work for some reason the machine is going to kick you into manual recovery mode if you've got an older"
- Watch: https://www.youtube.com/watch?v=2bRa6qm6wm4&t=129s
