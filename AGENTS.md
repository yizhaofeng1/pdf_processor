# ExamSplit AI Agent Rules

## Core Principle
AI identifies structure; local Python operates on the original PDF.

## Never
- Never regenerate final exam PDF from OCR text by default.
- Never trust raw model output without schema validation.
- Never modify the original PDF.
- Never hardcode one AI vendor into business logic.
- Never use fixed pixel coordinates as the persistent coordinate system.

## Always
- Use normalized coordinates (0.0 ~ 1.0) in persisted AI results.
- Preserve source PDF page and segment references.
- Validate all model outputs using Pydantic / JSON Schema.
- Make all AI results user-correctable.
- Write tests for coordinate transformations.
- Keep provider adapters isolated behind abstract interfaces.

## Preferred Stack
Python 3.11 + PySide6 + PyMuPDF (fitz) + Pydantic + SQLite.

## Quality Priority
Accuracy > source fidelity > recoverability > speed.
