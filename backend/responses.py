from pydantic import BaseModel

class ImageResponse(BaseModel):
    image_id: str
    metadata: dict
    histogram_id: str
