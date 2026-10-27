**The filesystem server you configured in Part 1 has access to every file under the path you specified. Identify two concrete risks this creates and explain how you would mitigate each risk.**



The first risk is that the server can change files and not just read them. Even though it is described as read only, it has tools like write\_file and edit\_file. To reduce this I would deny write tools in Claude Code's permission settings so only read tools are allowed. Using git diff can also catch unwanted changes and revert them if need be. The second risk would be the exposure of sensitive data such as tasks.db and any .env files that might hold passwords or API keys. To reduce this risk, I would keep secrets out of the project folder and isolate the server to folders and files it actually needs.



**The update\_task\_status tool writes to the database. Describe one attack scenario in which a malicious prompt could abuse this tool and explain how input validation or tool design could prevent it.**



A possible scenario is a hidden instruction that tries to get Claude to mark every task as completed but they are several things in the tool design that can prevent this. The Zod schema only accepts a positive whole number for the id and one of three allowed values for the status, so bad input like 3; DROP TABLE tasks is rejected before my code even runs. The ? queries prevent SQL injection, because user input is filled in safely and never becomes part of the SQL command itself. The database CHECK constraint prevents any status other than open, in\_progress, or completed from being saved, even if there were a bug in my code. Lastly, the tool only updates one task per call to prevent multiple changes happening at once.



**MCP servers run as local processes launched by Claude Code. What happens if the server crashes mid-request? How should a production MCP server handle partial failures?**



The tool call fails with an error, the connection between Claude Code and the server closes, and the server shows as failed in /mcp until it is restarted. A production server should use transactions so that any change involving multiple steps is all-or-nothing. It should also return clear error messages instead of crashing, so there is full visibility into what the tool did and what failed.

