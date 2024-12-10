from pydantic import BaseModel, Field, model_validator, field_validator
from typing import List, Tuple, Literal, Optional, Union

class GrayscaleOperation(BaseModel):
    operation_type: Literal['grayscale']
    mode: Literal['lightness', 'luminosity']

class HalftoningOperation(BaseModel):
    operation_type: Literal['halftoning']
    mode: Literal['grayscale', 'rgb']
    method: Literal['thresholding', 'error_diffusion']
    threshold: Union[int, Tuple[int, int, int]] = Field(None, description="Threshold value(s) for halftoning.")

    @model_validator(mode='after')
    def check_threshold(self):
        mode = self.mode
        threshold =self.threshold

        if mode == 'grayscale':
            if not isinstance(threshold, int):
                raise ValueError('For grayscale mode, threshold must be an integer between 0 and 255.')
            if not (0 <= threshold <= 255):
                raise ValueError('Threshold must be between 0 and 255 for grayscale mode.')
        elif mode == 'rgb':
            if not isinstance(threshold, tuple):
                raise ValueError('For RGB mode, threshold must be a tuple of three integers between 0 and 255.')
            if len(threshold) != 3:
                raise ValueError('Threshold tuple must have exactly three elements for RGB mode.')
            if not all(isinstance(t, int) and 0 <= t <= 255 for t in threshold):
                raise ValueError('Each threshold value must be an integer between 0 and 255.')
        return self

class HistogramEqualizationOperation(BaseModel):
    operation_type: Literal['histogram_equalization']
    mode: Literal['rgb', 'grayscale']

class HistogramSmoothingOperation(BaseModel):
    operation_type: Literal['histogram_smoothing']
    mode: Literal['rgb', 'grayscale']
    kernel_size: int = Field(3, ge=3, le=255, description="Kernel size for smoothing.")

    @model_validator(mode='after')
    def kernel_size(self):
        kernel_size = self.kernel_size

        if kernel_size % 2 == 0:
            raise ValueError('kernel_size must be an odd integer.')
        return self

class BasicEdgeDetectionOperation(BaseModel):
    operation_type: Literal['basic_edge_detection']
    operator: Literal['roberts', 'sobel', 'prewitt', 'kirsch', 'robinson', 'laplacian_1', 'laplacian_2']
    thresholding: bool
    contrast_based: bool
    threshold: Optional[int] = Field(None, ge=0, le=255, description="Threshold value for edge detection.")
    smoothing_kernel_size: Optional[int] = Field(None, ge=3, le=999, description="Kernel size for smoothing.")

    @model_validator(mode='after')
    def check_threshold_and_kernel_size(self):
        thresholding = self.thresholding
        threshold = self.threshold
        contrast_based = self.contrast_based
        smoothing_kernel_size = self.smoothing_kernel_size

        if thresholding and threshold is None:
            raise ValueError("'threshold' is required when 'thresholding' is True.")

        if contrast_based:
            if smoothing_kernel_size is None:
                raise ValueError("'smoothing_kernel_size' is required when 'contrast_based' is True.")
            if smoothing_kernel_size % 2 == 0:
                raise ValueError('smoothing_kernel_size must be an odd integer.')
        return self

class AdvancedEdgeDetectionOperation(BaseModel):
    operation_type: Literal['advanced_edge_detection']
    operator: Literal['homogeneity', 'difference', 'gaussian_1', 'gaussian_2', 'variance', 'range']
    contrast_based: bool
    smoothing_kernel_size: Optional[int] = Field(None, ge=3, le=999, description="Kernel size for smoothing.")
    thresholding: Optional[bool] = None
    threshold: Optional[int] = Field(None, ge=0, le=255, description="Threshold value for edge detection.")
    kernel_size: Optional[int] = Field(None, ge=3, le=999, description="Kernel size for the operator.")

    @model_validator(mode='after')
    def check_threshold_and_kernel_size(self):
        operator = self.operator
        threshold = self.threshold
        thresholding = self.thresholding
        contrast_based = self.contrast_based
        smoothing_kernel_size = self.smoothing_kernel_size
        kernel_size = self.kernel_size

        if contrast_based:
            if smoothing_kernel_size is None:
                raise ValueError("'smoothing_kernel_size' is required when 'contrast_based' is True.")
            if smoothing_kernel_size % 2 == 0:
                raise ValueError('smoothing_kernel_size must be an odd integer.')

        if operator in ['homogeneity', 'difference']:
            if threshold is None:
                raise ValueError(f"'threshold' is required for operator '{operator}'.")
            if contrast_based:
                raise ValueError(f"Cannot apply contrast-based edge detection to '{operator}'.")

        if operator in ['variance', 'range']:
            if kernel_size is None:
                raise ValueError(f"'kernel_size' is required for operator '{operator}'.")
            if kernel_size % 2 == 0:
                raise ValueError('kernel_size must be an odd integer.')

        return self

class FilteringOperation(BaseModel):
    operation_type: Literal['filtering']
    mode: Literal['high', 'low', 'median']
    kernel_size: int = Field(None, ge=3, le=999, description="Kernel size for filtering.")
    sigma: Optional[float] = Field(None, description="Sigma value for Gaussian filter.")

    @model_validator(mode='after')
    def check_sigma(self):
        mode = self.mode
        sigma = self.mode
        kernel_size = self.kernel_size
        if kernel_size % 2 == 0:
            raise ValueError('kernel_size must be an odd integer.')

        if mode == 'median' and sigma is not None:
            raise ValueError('Median filter does not require a sigma value.')

        return self

class MultiImageOperation(BaseModel):
    images: List
    operation_type: Literal['multi_image_operation']
    operation: Literal['add', 'subtract', 'cut_paste']
    src_region: Optional[Tuple[int, int, int, int]] = Field(None, description="Source region for 'cut_paste' operation.")
    dest_position: Optional[Tuple[int, int]] = Field(None, description="Destination position for 'cut_paste' operation.")

    @model_validator(mode='after')
    def check_fields_based_on_operation(self):
        images = self.images
        operation = self.operation
        src_region = self.src_region
        dest_position = self.dest_position

        if operation in ['add', 'subtract']:
            if src_region is not None or dest_position is not None:
                raise ValueError(f"Operation '{operation}' does not use 'src_region' or 'dest_position'.")
        elif operation == 'cut_paste':
            if len(images) != 2:
                raise ValueError("Operation 'cut_paste' requires exactly two images (source and destination).")
            if src_region is None or dest_position is None:
                raise ValueError("Operation 'cut_paste' requires 'src_region' and 'dest_position'.")
        return self

class SingleImageOperation(BaseModel):
    operation_type: Literal['single_image_operation']
    operation: Literal['rotate', 'flip', 'resize', 'invert']
    angle: Optional[float] = Field(None, description="Angle in degrees for rotation.")
    mode: Optional[Literal['horizontal', 'vertical']] = Field(None, description="Flip mode: 'horizontal' or 'vertical'.")
    output_size: Optional[Tuple[int, int]] = Field(None, description="Output size (width, height) for resizing.")

    @field_validator('output_size')
    @classmethod
    def validate_output_size(cls, v):
        if v is not None:
            if not (isinstance(v, tuple) and len(v) == 2):
                raise ValueError("'output_size' must be a tuple of two positive integers (width, height).")
            if not all(isinstance(dim, int) and dim > 0 for dim in v):
                raise ValueError("'output_size' dimensions must be positive integers.")
        return v

    @model_validator(mode='after')
    def check_fields_based_on_operation(self):
        operation = self.operation
        angle = self.angle
        mode = self.mode
        output_size = self.output_size

        if operation == 'rotate':
            if angle is None:
                raise ValueError("Operation 'rotate' requires 'angle' parameter.")
        elif operation == 'flip':
            if mode not in ['horizontal', 'vertical']:
                raise ValueError("Operation 'flip' requires 'mode' to be 'horizontal' or 'vertical'.")
        elif operation == 'resize':
            if output_size is None:
                raise ValueError("Operation 'resize' requires 'output_size' parameter.")
        return self

class CreateImageOperation(BaseModel):
    operation_type: Literal['create_image']
    width: int = Field(None, gt=0, description="Width of the image in pixels.")
    height: int = Field(None, gt=0, description="Height of the image in pixels.")
    color: Literal['white', 'black'] = Field(None, description="Background color of the image.")

class HistogramSegmentationOperation(BaseModel):
    operation_type: Literal['histogram_based_segmentation']
    mode: Literal['manual', 'peak', 'valley', 'adaptive'] = Field(None, description="Segmentation mode.")
    value: int = Field(None, ge=0, le=255, description="Pixel value to set for thresholded pixels.")
    segment: bool = Field(False, description="Whether to perform region growing.")
    hi: Optional[int] = Field(None, description="High threshold value for 'manual' mode.")
    low: Optional[int] = Field(None, description="Low threshold value for 'manual' mode.")

    @model_validator(mode='after')
    def check_fields_based_on_mode(self):
        mode = self.mode
        hi = self.hi
        low = self.low

        if mode == 'manual':
            if hi is None or low is None:
                raise ValueError("'hi' and 'low' must be set for manual mode.")
        return self

# Union of all operation models
from typing import Union

ImageOperation = Union[
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
    HistogramSegmentationOperation,
]
