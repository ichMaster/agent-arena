I need you to compare code in all branches excep main and provide statistics and scoring

branches naming convention
<Name of model set>-<Model for spec generation>-<Model for code generation>-dev

if there is no Model for code generation that means the branch was generated with the first model but step by step with stop and manual testing after each verison. Those 2 branches shoould be evalueate separately.



Request:
1) provide detailed code review for each
2) sumarize code review and evalueate on 3-4 criterias
3) evaluate quality of specification generated
4) aslo speed of code generation provided in code-generation-statistics.md or similar fine in some cases in root in some in implementation folder 
5) post code generation bugs provided in file post-code-generation-errors.md (if file is missed then were no bugs)
6) take into account my commnents and marks
7) provide magic quadrance with dimensions Speed-quality

My comments and marks:
Gemini-3.1Pro-dev
--
- Spec Generation: 4/5 Quality is good but I need to provide more details and focus on such areas as security, testing, roadmap structute etc
- UI Design Quality: 5/5 good qualtiy for the scratch
- Interactive development and fixes: 5/5 Antigravity 2.0 IDE fast, comprehencive, don't need to read all the time the comments from the model
- Bugs in code: 5/5 minor fixes

Anthropic-Opus4.8-dev	
--
- Spec Generation: 5/5 Quality is good from the first iteration
- UI Design Quality: 5/5 good qualtiy for the scratch
- Interactive development and fixes: 4/5 Opus4.5 generate lot's of text I have to read all the time
- Bugs in code: 5/5 minor fixes


Anthropic-Gemini3.1Pro-Sonet5-dev
--
- Interactive development and fixes: 4/5 Sonet5 generate lot's of text I have to read all the time

Anthropic-Opus4.8-Opus4.8-dev	
--
- Interactive development and fixes: 4/5 Sonet5 generate lot's of text I have to read all the time

Anthropic-Opus4.8-Sonet5-dev	
--
- Interactive development and fixes: 4/5 Sonet5 generate lot's of text I have to read all the time

Gemini-3.1Pro-3.1Pro-dev	
--
- Interactive development and fixes: 5/5 Quick and straght forward

Gemini-3.1Pro-3.5Flash-dev	
--
- Interactive development and fixes: 3/5 Spent lots of time explaining fixes, model has own position and argue
