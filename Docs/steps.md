Of course. Here are the detailed, step-by-step instructions for running your fully updated application.

I will provide two methods:

1.  **Method 1: Running Locally in Separate Terminals** (This is how you are currently working, but with the new database steps).
2.  **Method 2: Running with Docker Compose** (This is the recommended method for a smoother experience, as it manages all services—backend, frontend, and ChromaDB—for you).

---

### **Prerequisites (Do This Once)**

Before you start, make sure you have the following ready in your project's root directory (`sidhyaashu-talentlens/`):

1.  **Install Required Software:**
    *   Python 3.11+
    *   Docker and Docker Compose (for Method 2)

2.  **Create the `.env` file:**
    In the main project folder (`sidhyaashu-talentlens/`), create a file named `.env` and add your keys. This file is used by both the backend and Docker Compose.

    ```env
    # .env file

    # Your Gemini API Key from Google AI Studio
    GOOGLE_API_KEY="YOUR_GEMINI_API_KEY_HERE"

    # The Production Webhook URL you copied from your n8n workflow
    N8N_WEBHOOK_URL="YOUR_N8N_PRODUCTION_WEBHOOK_URL_HERE"
    ```

---

### **Method 1: Running Locally in Separate Terminals**

Use this method if you prefer not to use Docker and want to manage the processes yourself.

#### **Step 1: Set Up and Run the Backend**

You will need one terminal for the backend.

1.  **Navigate to the Backend Directory:**
    ```bash
    cd sidhyaashu-talentlens/backend
    ```

2.  **Create a Virtual Environment (Highly Recommended):**
    ```bash
    # Create the environment
    python -m venv venv

    # Activate it (on MacOS/Linux)
    source venv/bin/activate

    # Or activate it (on Windows)
    .\venv\Scripts\activate
    ```

3.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Initialize and Migrate the Database (Crucial New Step):**
    This only needs to be done once. These commands will create the `resume_analysis.db` file and set up all the necessary tables inside it.
    ```bash
    # Generate the migration script
    alembic revision --autogenerate -m "Initial migration"

    # Apply the migration to the database
    alembic upgrade head
    ```
    You should now see a new file named `resume_analysis.db` in your `backend` folder.

5.  **Run the FastAPI Server:**
    ```bash
    uvicorn app.main:app --reload
    ```
    Your backend is now running at `http://localhost:8000`. Leave this terminal open.

#### **Step 2: Set Up and Run the Frontend**

You will need a **second, new terminal** for the frontend.

1.  **Navigate to the Frontend Directory:**
    ```bash
    cd sidhyaashu-talentlens/frontend
    ```

2.  **Create a Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # (or .\venv\Scripts\activate on Windows)
    ```

3.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Streamlit Application:**
    ```bash
    streamlit run dashboard.py
    ```
    Your frontend dashboard will now open in your browser, usually at `http://localhost:8501`.

**You are now running!** You have two terminals open, one for the backend and one for the frontend, and you can use the application.

---

### **Method 2: Running with Docker Compose (Recommended)**

This method is simpler to manage once set up, as it handles starting and connecting all services automatically.

#### **Step 1: Build the Docker Images**

Open a single terminal in the **root directory** of your project (`sidhyaashu-talentlens/`).

1.  **Build the Docker images** for the backend, frontend, and ChromaDB as defined in your `docker-compose.yml`. This might take a few minutes the first time.
    ```bash
    docker-compose build
    ```

#### **Step 2: Run the Application and Database Migration**

1.  **Start all services in the background:**
    ```bash
    docker-compose up -d
    ```
    This command will start the backend, frontend, and ChromaDB containers. The `-d` flag runs them in "detached" mode.

2.  **Run the Database Migration Inside the Container (Crucial New Step):**
    Now that the backend container is running, we need to tell it to create and migrate the database.
    ```bash
    # Generate the migration script inside the 'backend' container
    docker-compose exec backend alembic revision --autogenerate -m "Initial migration"

    # Apply the migration inside the 'backend' container
    docker-compose exec backend alembic upgrade head
    ```
    This command executes the `alembic upgrade head` command *inside* the running `backend` service container.

**You are now running!** All services are running in the background.

#### **How to Use the Application with Docker:**

*   **Access the Frontend:** Open your browser and go to `http://localhost:8501`.
*   **Access the Backend API Docs:** Go to `http://localhost:8000/docs`.
*   **View Logs:** To see the logs from all running services (useful for debugging), use:
    ```bash
    docker-compose logs -f
    ```
    (Press `Ctrl + C` to stop viewing logs).
*   **Stop Everything:** To stop all the containers, run the following command from your project's root directory:
    ```bash
    docker-compose down
    ```


alembic init alembic
    alembic revision --autogenerate -m "Initial migration"
    alembic upgrade head