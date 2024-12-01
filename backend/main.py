from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import os
import shutil
import image_utils  # Assume this module contains implementations for all operations
from operations import (
    GrayscaleOperation,
    HalftoningOperation,
    HistogramEqualizationOperation,
    HistogramSmoothingOperation,
    BasicEdgeDetectionOperation,
    AdvancedEdgeDetectionOperation,
    FilteringOperation,
    MultiImageOperation,
    SingleImageOperation,
    CreateImageOperation,
    HistogramSegmentationOperation
)
from responses import ImageResponse

app = FastAPI(
    title="Image Processing API",
    description="An API for uploading images, applying transformations, and retrieving results. Developed as a project for Image Processing IT441 course at Helwan University. Developed by AHS",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.getcwd()
IMAGE_DIR = os.path.join(BASE_DIR, "images")
HISTOGRAM_DIR = os.path.join(BASE_DIR, "histograms")

for directory in [IMAGE_DIR, HISTOGRAM_DIR]:
    os.makedirs(directory, exist_ok=True)

@app.post("/images/", response_model=ImageResponse, status_code=201)
async def upload_image(file: UploadFile = File(...)):
    """
    Upload a new image.

    - **file**: Image file to upload.
    - **Returns**: Image ID, metadata, and histogram ID.
    """
    image_id = str(uuid4())
    image_filename = f"{image_id}.png"
    image_path = os.path.join(IMAGE_DIR, image_filename)
    histogram_path = os.path.join(HISTOGRAM_DIR, f"{image_id}.png")

    image_bytes = await file.read()

    png_image_bytes = image_utils.to_png_bytes(image_bytes)
    if isinstance(png_image_bytes, dict) and "error" in png_image_bytes:
        raise HTTPException(status_code=400, detail=png_image_bytes["error"])
    
    with open(image_path, "wb") as f:
        f.write(png_image_bytes.getvalue())
    
    metadata = image_utils.get_metadata(image_bytes, file.filename)
    if "error" in metadata:
        raise HTTPException(status_code=400, detail=metadata["error"])
    metadata['transformed'] = False # transformed flag

    histogram = image_utils.get_histograms(png_image_bytes.getvalue())
    if isinstance(histogram, dict) and "error" in histogram:
        raise HTTPException(status_code=400, detail=histogram["error"])
    
    with open(histogram_path, "wb") as f:
        f.write(histogram.getvalue())

    return ImageResponse(
        image_id = image_id,
        metadata = metadata,
        histogram_id = image_id
    )

@app.post("/images/create", response_model=ImageResponse, status_code=201)
def create_image(operation: CreateImageOperation):
    """
    Creates a new image with the specified size and color.
    
    - **width**: Width of the image in pixels.
    - **height**: Height of the image in pixels.
    - **color**: Background color ('white' or 'black').
    
    - **Returns**: Image ID, metadata, and histogram ID.
    """
    result = image_utils.create_image(operation)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    image_id = str(uuid4())
    image_filename = f"{image_id}.png"
    image_path = os.path.join(IMAGE_DIR, image_filename)
    histogram_path = os.path.join(HISTOGRAM_DIR, f"{image_id}.png")

    with open(image_path, "wb") as f:
        f.write(result.getvalue())

    
    image_bytes = result.getvalue()
    metadata = image_utils.get_metadata(image_bytes, image_filename)
    if "error" in metadata:
        raise HTTPException(status_code=400, detail=metadata["error"])
    metadata['transformed'] = False

    histogram = image_utils.get_histograms(image_bytes)
    if isinstance(histogram, dict) and "error" in histogram:
        raise HTTPException(status_code=400, detail=histogram["error"])
    
    with open(histogram_path, "wb") as f:
        f.write(histogram.getvalue())

    return ImageResponse(
        image_id = image_id,
        metadata = metadata,
        histogram_id = image_id
    )
    
@app.get("/images/{image_id}", response_class=StreamingResponse)
def get_image(image_id: str):
    """
    Retrieve an uploaded image.

    - **image_id**: ID of the image to retrieve.
    - **Returns**: Image file as PNG.
    """
    image_path = get_image_path(image_id)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path, media_type="image/png")


@app.get("/images/{image_id}/histogram", response_class=FileResponse)
def get_histogram(image_id: str):
    """
    Retrieve the histogram of an image.

    - **image_id**: ID of the image.
    - **Returns**: Histogram image as PNG.
    """
    histogram_path = os.path.join(HISTOGRAM_DIR, f"{image_id}.png")
    if not os.path.exists(histogram_path):
        raise HTTPException(status_code=404, detail="Histogram not found")
    return FileResponse(histogram_path, media_type="image/png")

@app.delete("/images/{image_id}", status_code=204)
def delete_image(image_id: str):
    """
    Delete an uploaded image.

    - **image_id**: ID of the image to delete.
    """
    image_path = get_image_path(image_id)
    if os.path.exists(image_path):
        os.remove(image_path)
        histogram_path = os.path.join(HISTOGRAM_DIR, f"{image_id}.png")
        if os.path.exists(histogram_path):
            os.remove(histogram_path)
    else:
        raise HTTPException(status_code=404, detail="Image not found")
    return

@app.post("/images/{image_id}/grayscale", response_model=ImageResponse, status_code=201)
async def apply_grayscale(image_id: str, operation: GrayscaleOperation = Body(...)):
    """
    Apply grayscale transformation.

    - **image_id**: ID of the image to transform.
    - **operation**: Grayscale operation parameters.
    - **Returns**: Transformed image ID, metadata, and histogram ID.

    """
    return await apply_transformation(image_id, operation, 'grayscale')

@app.post("/images/{image_id}/halftoning", response_model=ImageResponse, status_code=201)
async def apply_halftoning(image_id: str, operation: HalftoningOperation = Body(...)):
    """
    Apply halftoning transformation.

    - **image_id**: ID of the image to transform.
    - **operation**: Halftoning operation parameters.
    - **Returns**: Transformed image ID, metadata, and histogram ID.

    """
    return await apply_transformation(image_id, operation, 'halftoning')

@app.post("/images/{image_id}/histogram_equalization", response_model=ImageResponse, status_code=201)
async def apply_equalization(image_id: str, operation: HistogramEqualizationOperation = Body(...)):
    """
    Apply histogram equalization.

    - **image_id**: ID of the image to transform.
    - **operation**: Equalization operation parameters.
    - **Returns**: Transformed image ID, metadata, and histogram ID.

    """
    return await apply_transformation(image_id, operation, 'histogram_equalization')

@app.post("/images/{image_id}/histogram_smoothing", response_model=ImageResponse, status_code=201)
async def apply_equalization(image_id: str, operation: HistogramSmoothingOperation = Body(...)):
    """
    Apply histogram smoothing.

    - **image_id**: ID of the image to transform.
    - **operation**: Smoothinh operation parameters.
    - **Returns**: Transformed image ID, metadata, and histogram ID.

    """
    return await apply_transformation(image_id, operation, 'histogram_smoothing')

@app.post("/images/{image_id}/basic_edge_detection", response_model=ImageResponse, status_code=201)
async def apply_basic_edge_detection(image_id: str, operation: BasicEdgeDetectionOperation = Body(...)):
    """
    Apply basic edge detection.

    - **image_id**: ID of the image to transform.
    - **operation**: Basic edge detection parameters.
    - **Returns**: Transformed image ID, metadata, and histogram ID.

    """
    return await apply_transformation(image_id, operation, 'basic_edge_detection')

@app.post("/images/{image_id}/advanced_edge_detection", response_model=ImageResponse, status_code=201)
async def apply_advanced_edge_detection(image_id: str, operation: AdvancedEdgeDetectionOperation = Body(...)):
    """
    Apply advanced edge detection.

    - **image_id**: ID of the image to transform.
    - **operation**: Advanced edge detection parameters.
    - **Returns**: Transformed image ID, metadata, and histogram ID.

    """
    return await apply_transformation(image_id, operation, 'advanced_edge_detection')

@app.post("/images/{image_id}/filtering", response_model=ImageResponse, status_code=201)
async def apply_filtering(image_id: str, operation: FilteringOperation = Body(...)):
    """
    Apply filtering operation.

    - **image_id**: ID of the image to transform.
    - **operation**: Filtering operation parameters.
    - **Returns**: Transformed image ID, metadata, and histogram ID.

    """
    return await apply_transformation(image_id, operation, 'filtering')

@app.post("/images/{image_id}/single_operation", response_model=ImageResponse, status_code=201)
async def apply_single_image_operation(image_id: str, operation: SingleImageOperation = Body(...)):
    """
    Apply single image operation (rotate, flip, scale, invert).

    - **image_id**: ID of the image to transform.
    - **operation**: Single image operation parameters.
    - **Returns**: Transformed image ID, metadata, and histogram ID.

    """
    return await apply_transformation(image_id, operation, 'single_operation')

@app.post("/images/multi_operation", response_model=ImageResponse, status_code=201)
async def apply_multi_image_operation(operation: MultiImageOperation = Body(...)):
    """
    Apply multi-image operation (add, subtract, cut_paste).

    - **operation**: Multi-image operation parameters.
    - **Returns**: Transformed image ID, metadata, and histogram ID.

    """
    return await apply_multi_transformation(operation)

def get_image_path(image_id: str):
    image_file_name = f"{image_id}.png"
    image_path = os.path.join(IMAGE_DIR, image_file_name)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return image_path

@app.post("/images/{image_id}/histogram_segmentation", status_code=201)
async def apply_histogram_segmentation(image_id: str, operation: HistogramSegmentationOperation = Body(...)):
    """
    Apply histogram-based segmentation.

    - **image_id**: ID of the image to transform.
    - **operation**: Segmentation operation parameters.
    - **Returns**: Transformed image.
    """
    return await apply_transformation(image_id, operation, 'histogram_segmentation')

async def apply_transformation(image_id: str, operation, operation_type: str):
    image_path = get_image_path(image_id)

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    if operation_type == 'grayscale':
        result = image_utils.apply_grayscale(image_bytes, operation)
    elif operation_type == 'halftoning':
        result = image_utils.apply_halftoning(image_bytes, operation)
    elif operation_type == 'histogram_equalization':
        result = image_utils.apply_histogram_equalization(image_bytes, operation)
    elif operation_type == 'histogram_smoothing':
        result = image_utils.apply_histogram_smoothing(image_bytes, operation)
    elif operation_type == 'basic_edge_detection':
        result = image_utils.apply_basic_edge_detection(image_bytes, operation)
    elif operation_type == 'advanced_edge_detection':
        result = image_utils.apply_advanced_edge_detection(image_bytes, operation)
    elif operation_type == 'filtering':
        result = image_utils.apply_filtering(image_bytes, operation)
    elif operation_type == 'single_operation':
        result = image_utils.apply_single_image_operation(image_bytes, operation)
    elif operation_type == 'histogram_segmentation':
        result = image_utils.apply_histogram_segmentation(image_bytes, operation)
    else:
        raise HTTPException(status_code=400, detail="Unsupported operation type")

    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    transformed_image_id = str(uuid4())
    transformed_image_filename = f"{transformed_image_id}.png"
    transformed_image_path = os.path.join(IMAGE_DIR, transformed_image_filename)
    with open(transformed_image_path, "wb") as f:
        f.write(result.getvalue())

    transformed_image_bytes = result.getvalue()
    metadata = image_utils.get_metadata(transformed_image_bytes, transformed_image_filename)
    if "error" in metadata:
        raise HTTPException(status_code=400, detail=metadata["error"])
    metadata['transformed'] = True

    histogram = image_utils.get_histograms(transformed_image_bytes)
    if isinstance(histogram, dict) and "error" in histogram:
        raise HTTPException(status_code=400, detail=histogram["error"])
    histogram_path = os.path.join(HISTOGRAM_DIR, f"{transformed_image_id}.png")
    with open(histogram_path, "wb") as f:
        f.write(histogram.getvalue())

    return ImageResponse(
        image_id = transformed_image_id,
        metadata = metadata,
        histogram_id = transformed_image_id
    )

async def apply_multi_transformation(operation: MultiImageOperation):
    image_bytes_list = []
    for image_id in operation.images:
        image_path = get_image_path(image_id)
        with open(image_path, "rb") as f:
            image_bytes_list.append(f.read())

    result = image_utils.apply_multi_image_operation(image_bytes_list, operation)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    transformed_image_id = str(uuid4())
    transformed_image_filename = f"{transformed_image_id}.png"
    transformed_image_path = os.path.join(IMAGE_DIR, transformed_image_filename)
    with open(transformed_image_path, "wb") as f:
        f.write(result.getvalue())

    transformed_image_bytes = result.getvalue()
    metadata = image_utils.get_metadata(transformed_image_bytes, transformed_image_filename)
    if "error" in metadata:
        raise HTTPException(status_code=400, detail=metadata["error"])
    metadata['transformed'] = True

    histogram = image_utils.get_histograms(transformed_image_bytes)
    if isinstance(histogram, dict) and "error" in histogram:
        raise HTTPException(status_code=400, detail=histogram["error"])
    histogram_path = os.path.join(HISTOGRAM_DIR, f"{transformed_image_id}.png")
    with open(histogram_path, "wb") as f:
        f.write(histogram.getvalue())

    return ImageResponse(
        image_id = transformed_image_id,
        metadata = metadata,
        histogram_id = transformed_image_id
    )

