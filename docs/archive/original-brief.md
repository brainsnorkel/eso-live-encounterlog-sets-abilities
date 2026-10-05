I want a simple mac/windows cli tool that runs continuously, tailing an ESO encounterlog and after each combat ends in the tailed log, it prints out the character handles if available (anon if not), their inferred subclass setup, bar abilities, a summary of the gear they have on.

An ESO log format description is here: 
https://github.com/sheumais/logs/blob/master/parser/README.md

A database of sets is here:
https://github.com/Baertram/LibSets/tree/LibSets-reworked/LibSets/Data


For testing, I have some logs in the esample-log folder. To test the tool, maybe have a mode that self-tails the log to itself to similate a live logging situation. 


