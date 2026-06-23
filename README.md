# Software Quality Evaluation Tool
> Automated ISO/IEC 25010 Performance Efficiency evaluator for Java Spring Boot applications

## Overview
This tool allows developers to upload a Java project zip file and receive a quality report evaluated against the standard and definitions stated in ISO/IEC 25010. This tool automatically builds the project, runs it in an isolated environment, performs load testing, and uses AI to produce findings and recommendations.

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


---

## Installation

