import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import Database from 'better-sqlite3';
import { z } from 'zod';
import path from 'path';
import { fileURLToPath } from 'url';
const thisFolder = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH = path.resolve(thisFolder, '../../taskmanager/tasks.db');

const server = new McpServer({
  name: 'task-db-server',
  version: '1.0.0',
});

// ---------------- Tool A: tasks_by_status ----------------

const tasksByStatusSchema = z.object({
  status: z.enum(['open', 'in_progress', 'completed'])
    .describe('Filter tasks by this status value'),
});

server.registerTool(
  'tasks_by_status',
  {
    description: 'List all tasks with the given status',
    inputSchema: tasksByStatusSchema.shape,
  },
  async ({ status }) => {
    const db = new Database(DB_PATH, { readonly: true, fileMustExist: true });

    try {
      const rows = db
        .prepare('SELECT id, title, assigned_to, due_date FROM tasks WHERE status = ?')
        .all(status);

      if (rows.length === 0) {
        return {
          content: [{ type: 'text', text: 'No tasks found for status: ' + status }],
        };
      }

      let table = 'ID  | Title                    | Assigned To | Due Date\n';
      table += '----+--------------------------+-------------+-----------\n';

      for (const row of rows) {
        table +=
          String(row.id).padEnd(3) + ' | ' +
          row.title.padEnd(24) + ' | ' +
          row.assigned_to.padEnd(11) + ' | ' +
          row.due_date + '\n';
      }

      return {
        content: [{ type: 'text', text: table }],
      };
    } finally {
      db.close();
    }
  }
);

// ---------------- Tool B: update_task_status ----------------

const updateTaskStatusSchema = z.object({
  id: z.number().int().positive().describe('Task ID to update'),
  status: z.enum(['open', 'in_progress', 'completed'])
    .describe('New status value'),
});

server.registerTool(
  'update_task_status',
  {
    description: 'Change the status of one task by its id',
    inputSchema: updateTaskStatusSchema.shape,
  },
  async ({ id, status }) => {
    const db = new Database(DB_PATH, { fileMustExist: true });

    try {
      const result = db
        .prepare('UPDATE tasks SET status = ? WHERE id = ?')
        .run(status, id);

      if (result.changes === 0) {
        return {
          content: [{ type: 'text', text: 'Task ' + id + ': not found' }],
        };
      }

      return {
        content: [{ type: 'text', text: 'Task ' + id + ' updated to status: ' + status }],
      };
    } finally {
      db.close();
    }
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
console.error('task-db-server is running');
