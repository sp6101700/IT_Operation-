# Kestrel IT Operations & Helpdesk Automation Portal

A runnable demo website with:
- Manual single-employee entry (no Excel required)
- Five working demo automation jobs
- One RabbitMQ message per job click
- A Python RabbitMQ consumer that processes messages individually
- SQLite persistence and live status refresh
- Excel is optional; this starter version does not require it

## Requirements
- Windows 10/11
- Python 3.10+
- RabbitMQ Server running locally
- RabbitMQ Management plugin optional (for the browser console)

## Start RabbitMQ
Make sure the RabbitMQ Windows service is running. If you use the management console, open:
http://localhost:15672
Default local development credentials are usually `guest` / `guest`.

The app expects RabbitMQ at `localhost` with user `guest` and password `guest`.
For a remote broker, set environment variables `RABBITMQ_HOST`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`.

## Run the website (Windows)
1. Extract this ZIP.
2. Open the extracted `kestrel_it_automation` folder in VS Code.
3. Open Terminal in that folder.
4. Create a virtual environment (recommended):

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\activate
   ```

5. Install packages:

   ```powershell
   python -m pip install -r requirements.txt
   ```

6. Start the app:

   ```powershell
   python -m uvicorn app:app --host 127.0.0.1 --port 8000
   ```

7. Open this URL:

   http://127.0.0.1:8000

Keep this terminal open. It runs the FastAPI backend and the RabbitMQ consumer thread.
Do not open `index.html` directly or use Live Server; the page must be served by FastAPI.

## Test one employee and one RabbitMQ message
1. Confirm RabbitMQ is running.
2. Open the website.
3. Add one employee, for example:
   - Employee ID: KLG001
   - First Name: Asha
   - Last Name: Rao
   - Department: HR
4. Select Asha in the Employee dropdown.
5. Click `Run job` on `Login ID Creation`.
6. The Activity table should show one message and then `Completed`.
7. Run a different job to send another separate message.

## Five demo jobs
1. Login ID Creation: generates a login ID from the employee's name.
2. Account Creation: creates a demo account ID and temporary password.
3. Access Request: creates a request reference with `Pending Approval`.
4. Password Reset: generates a demo reset reference and temporary password.
5. Helpdesk Ticket: creates an open ticket with category and issue.

## Important notes
- This is a local demonstration, not a production identity or helpdesk system.
- Account creation and password reset are simulated. They do not create real Windows/AD/email accounts or change real passwords.
- Access requests are recorded as pending approval; no real permissions are granted.
- Temporary credentials are demo-only. Do not reuse them.
- For a real Agentix integration, configure Agentix to consume the same RabbitMQ queue or call the API. Do not run two competing consumers on the same queue unless that is intended; RabbitMQ distributes messages between consumers.
- Data is stored locally in `automation.db`. Back up that file if you need to preserve demo records.
