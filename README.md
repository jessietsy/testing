# Software Quality Evaluation Tool
> Automated ISO/IEC 25010 Performance Efficiency evaluator for Java Spring Boot applications

## Overview
This tool allows developers to upload a Java project zip file and receive a quality report evaluated against the standard and definitions of Performance Efficiency stated in ISO/IEC 25010. This tool automatically builds the project, runs it in an isolated environment, performs load testing, and uses AI to produce findings and recommendations.

---

## How it works
1. Developer uploads Java Spring Boot zip file through the web interface
2. The tool detects meta data from the files (including build system, Java version, HTTP endpoints etc.) automatically
3. The project is built and run inside an isolated Docker container 
4. Locust performs a load test simulating concurrent users hitting the detected endpoints
5. Each endpoint is categorised and scored against category-specific ISO thresholds
6. The LLM API interprets the scores and generates plain English findings and recommendations 
7. Results are displayed and saved to a local database

---

## Requirements
- Docker Desktop (Running)
- Python 3.10+ (Tested on Python 3.10)
- Git

---

## Installation
1.  Clone the repository

```bash
git clone https://github.com/jessietsy/testing.git
cd testing
```

2. Create virtual environment

```bash
python -m venv venv

# Mac/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Set API key 

This tool uses the Google Gemini API for AI Evaluation. Get a key at https://aistudio.google.com/api-keys then set it as an environmental variable

```bash
# Mac/Linux
export GEMINI_API_KEY='your-key-here'

# Windows
set GEMINI_API_KEY=your-key-here
```

5. Make sure Docker Desktop is running

Open Docker Desktop and wait for it to fully start before running this tool

---

## Running the tool

```bash
python app.py
```

Then open your browser and visit:
http://localhost:5000

---

## What to upload 

The tool currently supports **Java Spring Boot projects** built with **Maven** or **Gradle**. The project should 
- Expose HTTP endpoints via Spring MVC annotation (`@GetMapping`, `@PostMapping` etc)
- Upload project as zip file

---


## Future development
- Additional language support
- Additional ISO/IEC 25010 characteristics
- Scenario-based testing - integrating with functional suitablity output to evaluate performance per user flow
- Data seeding - automatically inserting test data into database before load testing so all endpoint types are exercised meaningfully