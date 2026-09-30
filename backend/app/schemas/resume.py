from pydantic import BaseModel, Field


class ResumeParseResponse(BaseModel):
    """
    The shape of the JSON we send back after parsing a resume.

    Pydantic validates that our route actually returns these fields with
    the right types — if we forget one, Python raises an error immediately
    rather than sending broken JSON to the client.
    """

    text: str = Field(
        description="Cleaned text extracted from the resume PDF."
    )
    page_count: int = Field(
        description="Number of pages in the uploaded PDF."
    )
    char_count: int = Field(
        description="Number of characters in the returned text (after truncation)."
    )
