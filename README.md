# Hikma Order Automation System

An AI-assisted pharmaceutical order automation system designed to transform unstructured WhatsApp-style customer orders into structured, validated, and ready-to-process order data.

## Overview

Hikma was built to solve a real operational problem in pharmaceutical order processing. Customer orders often arrive as unstructured text with different product names, quantities, bonuses, dosages, abbreviations, and notes.

The system processes these orders, identifies and matches products, applies business rules, validates product strengths, and generates structured Excel output for further processing.

The application is deployed and used in a real daily business workflow, processing approximately 8–10 orders per day.

## Key Features

- Processes unstructured WhatsApp-style pharmaceutical orders
- Arabic text normalization
- Product name and alias matching
- Fuzzy product matching
- Dosage and strength validation
- Equivalent strength detection such as 1G = 1000MG
- Quantity and bonus extraction
- Pricing and transit-product rules
- Order notes handling
- Match classifications:
  - Matched
  - Fuzzy
  - Ambiguous
  - Unmatched
  - Strength Conflict
- Automated structured Excel output

## Architecture

User Order
→ Frontend
→ REST API
→ Python Backend
→ Order Parsing & Business Rules
→ Product Matching & Validation
→ Excel Output

## Tech Stack

### Backend
- Python
- REST API
- Data processing
- Product matching
- Business rule automation
- Excel generation

### Frontend
- React
- Vite

### Deployment
- Render

## Real-World Usage

The system has been deployed and used in a real pharmaceutical business workflow.

It processes approximately **8–10 orders per day**, reducing repetitive manual order processing and standardizing order output.

## Project Structure

- `backend/` — API, order-processing logic, product matching, validation, and Excel generation
- `frontend/` — User interface
- `DEPLOYMENT.md` — Deployment documentation
- `RELEASE_NOTES.md` — Release information

## Purpose

This project demonstrates practical experience in:

- Business process automation
- Python backend development
- REST API development
- Natural-language order processing
- Data validation and matching
- Translating real business requirements into a deployed software solution
