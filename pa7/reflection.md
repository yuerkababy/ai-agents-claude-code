**Describe one decision you made while designing your tool schemas (e.g., choosing an enum vs. a free-text field) and explain the trade-offs.**



For both tools, I used a Zod enum for the status field instead of a free-text string, so it only accepts open, in\_progress, or completed. The main benefit is safety and consistency. Claude can’t send a typo like "done" or "Completed", and it can’t sneak in anything strange because the input is rejected before my code runs. The enum also shows up in the tool’s schema, so Claude knows exactly which values are allowed without me having to explain them. The trade-off is flexibility. If the project ever needs a new status, I would have to update the enum in both tools and the database’s CHECK constraint. For this project, I think the extra safety is worth that.



**How does the MCP approach compare to calling a REST API from within a Claude Code prompt? What are the advantages and limitations of each?**



With MCP, my tools are registered once, and Claude Code automatically knows their names, descriptions, and input schemas. Claude can call them directly and the inputs are validated. The hypothetically database credentials stay inside my server, so Claude never sees. The limitations are that I had to build and configure a server that runs locally.



Calling a REST API from a prompt needs no extra server and works with any existing API. However, Claude has to build the request correctly every time, there’s no schema checking the input so it’s easier for a bad prompt to send the wrong request.



**Identify one capability you wish your custom server had and describe how you would implement it as a third MCP tool.**



I would add a create task tool so Claude can add new tasks. Its Zod schema would take a title with a max length, assigned to variable, and a due date that matches the YYYY-MM-DD format. The handler would have the database open and then run a parameterized a INSERT INTO tasks (title, assigned\_to, due\_date, status) VALUES (?, ?, ?, 'open'). It would then close the database and return the Task id created. Status is not one of the inputs, because it is important that new tasks always start as open. That way, Claude cannot create a task that is already marked completed.
