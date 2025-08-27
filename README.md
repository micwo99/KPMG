# README for Home Assignment GenAI KPMG

## Overview
This project is divided into two main parts:

### Part 1
Part 1 contains the following files:
- `app_streamlit.py`: Streamlit application for user interaction.
- `extract_fields.py`: Script for extracting specific fields from data.
- `prompt.py`: Contains logic for generating prompts.
- `test.py`: Unit tests for validating the functionality.
- `validators.py`: Validation logic for ensuring data integrity.

### Part 2
Part 2 is further divided into two subdirectories:

#### Client
- `ui_streamlit.py`: Streamlit application for the client-side interface.

#### Server
- `kb_index.py`: Logic for building and searching the knowledge base index.
- `logger.py`: Logging utility for tracking application events.
- `main.py`: Entry point for the server-side application.
- `models.py`: Contains data models used in the application.
- `prompts.py`: Logic for generating prompts on the server side.

## Setup
To set up the project, follow these steps:

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   - Create a `.env` file in the root directory.
   - Add the necessary variables (e.g., `API_BASE`, `AZURE_OPENAI_ENDPOINT`, etc.).

3. Run the applications:
   - For Part 1: Execute `app_streamlit.py`.
   - For Part 2: Start the server using `main.py` and the client using `ui_streamlit.py`.

## How to Run Each Part

### Part 1
To run Part 1, execute the following command:
```bash
streamlit run part1/app_streamlit.py
```
Ensure that the required dependencies are installed and the `.env` file is properly configured.

### Part 2
Part 2 consists of a server and a client. Follow these steps:

#### Server
To start the server, run:
```bash
python part2/server/main.py
```

#### Client
To start the client-side Streamlit application, run:
```bash
streamlit run part2/client/ui_streamlit.py
```

Make sure the server is running before starting the client application.

## Dependencies
All dependencies are listed in the `requirements.txt` file.

## Folder Structure
```
Home-Assignment-GenAI-KPMG/
├── part1/
│   ├── app_streamlit.py
│   ├── extract_fields.py
│   ├── prompt.py
│   ├── test.py
│   ├── validators.py
│   └── __pycache__/
├── part2/
│   ├── client/
│   │   └── ui_streamlit.py
│   ├── server/
│   │   ├── kb_index.py
│   │   ├── logger.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── prompts.py
│   │   └── __pycache__/
├── phase1_data/
├── phase2_data/
├── README.md
└── requirements.txt
```

## Notes
- Ensure that the `.env` file is properly configured before running the applications.
- The project is designed to work with Streamlit for the UI and Python for backend logic.
