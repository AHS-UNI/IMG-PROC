from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import io
import json
import image_utils 
from operations import (
    ImageOperation,
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
from typing import Dict, List

app = FastAPI(
    title="IMG-PROC",
    description="A stateless image processing API. Developed by AHS",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://0.0.0.0:8080/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/to_png")
async def to_png(file: UploadFile = File(...)):
    """
    Converts images to PNG format.

    - **file**: Image file.
    - **Returns**: Image as PNG.
    """
    
    image_bytes = await file.read()
    result = image_utils.to_png_bytes(image_bytes)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    image_bytes = result.getvalue()

    return StreamingResponse(io.BytesIO(image_bytes), media_type="image/png")

@app.post("/create_image")
async def create_image(operation_data: CreateImageOperation):
    """
    Creates a new image with the specified size and color.

    - **operation_data**: Parameters for creating the image.
    - **Returns**: Created image as PNG.
    """

    result = image_utils.create_image(operation_data)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    image_bytes = result.getvalue()

    return StreamingResponse(io.BytesIO(image_bytes), media_type="image/png")

@app.post("/histogram")
async def get_histogram(file: UploadFile = File(...)):
    """
    Computes and returns the histogram of the provided image.

    - **file**: Image file to analyze.
    - **Returns**: Histogram image as PNG.
    """
    image_bytes = await file.read()
    histogram = image_utils.get_histograms(image_bytes)
    if isinstance(histogram, dict) and "error" in histogram:
        raise HTTPException(status_code=400, detail=histogram["error"])
    
    return StreamingResponse(io.BytesIO(histogram.getvalue()), media_type="image/png")

@app.post("/metadata")
async def get_metadata(file: UploadFile = File(...)):
    """
    Retrieves metadata of the provided image.

    - **file**: Image file to extract metadata from.
    - **Returns**: Image metadata.
    """
    image_bytes = await file.read()
    metadata = image_utils.get_metadata(image_bytes, file.filename)
    if "error" in metadata:
        raise HTTPException(status_code=400, detail=metadata["error"])
    
    return metadata

@app.post("/transform")
async def transform_image(file: UploadFile = File(...), operation_data: str = Form(...)):
    """
    Applies a transformation to the provided image.

    - **file**: Image file to transform.
    - **operation_data**: Operation parameters including 'operation_type'.
    - **Returns**: Transformed image as PNG.
    """
    try:
        operation_dict = json.loads(operation_data)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON for operation_data: {str(e)}")
    
    image_bytes = await file.read()
    operation_type = operation_dict.get('operation_type')
    if not operation_type:
        raise HTTPException(status_code=400, detail="operation_type is required.")
    
    operation = parse_operation(operation_dict)
    transformed_image = await apply_transformation(image_bytes, operation, operation_type)
    return StreamingResponse(io.BytesIO(transformed_image), media_type="image/png")

@app.post("/tranform_multi")
async def transform_multi_image(files: List[UploadFile] = File(...), operation_data: str = Form(...)):
    """
    Applies a transformation that involves multiple images.

    - **files**: List of image files to transform.
    - **operation_data**: Operation parameters including 'operation_type'.
    - **Returns**: Transformed image as PNG.
    """
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="At least two image files must be provided.")
    
    try:
        operation_dict = json.loads(operation_data)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON for operation_data: {str(e)}")
    
    operation_type = operation_dict.get('operation_type')
    if not operation_type:
        raise HTTPException(status_code=400, detail="operation_type is required.")
    
    image_bytes_list = []
    for idx, file in enumerate(files):
        try:
            image_bytes = await file.read()
            image_bytes_list.append(image_bytes)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading file {idx + 1}: {str(e)}")
        
    operation = parse_multi_operation(image_bytes_list, operation_dict)
    
    transformed_image = await apply_multi_transformation(operation, operation_type)
    return StreamingResponse(io.BytesIO(transformed_image), media_type="image/png")

def parse_operation(operation_data: dict) -> ImageOperation:
    """
    Parses the operation data into the corresponding ImageOperation.

    - **operation_data**: Dictionary containing operation parameters.
    - **Returns**: An instance of ImageOperation.
    """
    operation_type = operation_data.get('operation_type')

    operation_classes = {
        'grayscale': GrayscaleOperation,
        'halftoning': HalftoningOperation,
        'histogram_equalization': HistogramEqualizationOperation,
        'histogram_smoothing': HistogramSmoothingOperation,
        'basic_edge_detection': BasicEdgeDetectionOperation,
        'advanced_edge_detection': AdvancedEdgeDetectionOperation,
        'filtering': FilteringOperation,
        'single_image_operation': SingleImageOperation,
        'histogram_based_segmentation': HistogramSegmentationOperation,
        'create_image': CreateImageOperation,
    }

    operation_class = operation_classes.get(operation_type)
    if not operation_class:
        raise HTTPException(status_code=400, detail=f"Unsupported operation_type '{operation_type}'.")

    try:
        operation = operation_class(**operation_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return operation

def parse_multi_operation(image_list: List, operation_data: dict) -> MultiImageOperation:
    """
    Parses the operation data into the corresponding MultiImageOperation.

    - **operation_data**: Dictionary containing operation parameters.
    - **Returns**: An instance of MultiImageOperation.
    """
    operation_type = operation_data.get('operation_type')

    if operation_type != 'multi_image_operation':
        raise HTTPException(status_code=400, detail=f"Unsupported operation_type '{operation_type}' for multi-image transformation.")

    operation_data['images'] = image_list

    try:
        operation = MultiImageOperation(**operation_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return operation

async def apply_transformation(image_bytes: bytes, operation: ImageOperation, operation_type: str) -> bytes:
    """
    Applies the specified transformation to the image bytes.

    - **image_bytes**: Original image bytes.
    - **operation**: Parsed ImageOperation instance.
    - **operation_type**: Type of operation to apply.
    - **Returns**: Transformed image bytes.
    """
    operation_functions = {
        'grayscale': image_utils.apply_grayscale,
        'halftoning': image_utils.apply_halftoning,
        'histogram_equalization': image_utils.apply_histogram_equalization,
        'histogram_smoothing': image_utils.apply_histogram_smoothing,
        'basic_edge_detection': image_utils.apply_basic_edge_detection,
        'advanced_edge_detection': image_utils.apply_advanced_edge_detection,
        'filtering': image_utils.apply_filtering,
        'single_image_operation': image_utils.apply_single_image_operation,
        'histogram_based_segmentation': image_utils.apply_histogram_based_segmentation,
    }

    apply_function = operation_functions.get(operation_type)
    if not apply_function:
        raise HTTPException(status_code=400, detail="Unsupported operation type.")

    result = apply_function(image_bytes, operation)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    transformed_image_bytes = result.getvalue()
    return transformed_image_bytes

async def apply_multi_transformation(operation: MultiImageOperation, operation_type: str) -> bytes:
    """
    Applies the specified multi-image transformation.

    - **image_bytes_list**: List of image bytes.
    - **operation**: Parsed MultiImageOperation instance.
    - **Returns**: Transformed image bytes.
    """
    result = image_utils.apply_multi_image_operation(operation)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    if not isinstance(result, io.BytesIO):
        raise HTTPException(status_code=500, detail="Unexpected error during multi-image transformation.")

    transformed_image_bytes = result.getvalue()
    return transformed_image_bytes