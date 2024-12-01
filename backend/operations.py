from pydantic import BaseModel, Field, model_validator, field_validator
from typing import List, Tuple, Literal, Optional, Union

class GrayscaleOperation(BaseModel):
    mode: Literal['lightness', 'luminosity']

class RGBOperation(BaseModel):
    pass

class HalftoningOperation(BaseModel):
    mode: Literal['grayscale', 'RGB']
    method: Literal['thresholding', 'error_diffusion']
    threshold: Union[int, Tuple[int, int, int]] = Field(...)

    @model_validator(mode='after')
    def check_threshold(self):
        if self.mode == 'grayscale':
            if not isinstance(self.threshold, int):
                raise ValueError('For grayscale mode, threshold must be an integer.')
            if not (0 <= self.threshold <= 255):
                raise ValueError('Threshold must be between 0 and 255 for grayscale mode.')
        elif self.mode == 'RGB':
            if not isinstance(self.threshold, tuple):
                    raise ValueError('For RGB halftoning, threshold must be a tuple of three integers.')
            if len(self.threshold) != 3:
                    raise ValueError('Threshold tuple must have exactly three elements for RGB mode.')
            if not all(isinstance(t, int) and 0 <= t <= 255 for t in self.threshold):
                    raise ValueError('Each threshold value must be an integer between 0 and 255.')
        return self
    
class HistogramEqualizationOperation(BaseModel):
    mode: Literal['RGB', 'grayscale']

class HistogramSmoothingOperation(BaseModel):
    mode: Literal['RGB', 'grayscale']
    kernel_size: int = Field(ge=0, le=255)

class BasicEdgeDetectionOperation(BaseModel):
    operator: Literal['roberts', 'sobel', 'prewitt', 'kirsch', 'robinson', 'laplacian_1', 'laplacian_2']
    thresholding: bool
    contrast_based: bool
    threshold: Optional[int] = Field(None,ge=0, le=255)
    smoothing_kernel_size: Optional[int] = Field(None, ge=3, le=999)
    
    @model_validator(mode='after')
    def check_threshold_and_kernel_size(self):
        if self.thresholding:
            if self.threshold is None:
                raise ValueError(f"'threshold' is required when 'thresholding' is True")
        
        if self.contrast_based:
            if self.smoothing_kernel_size is None:
                raise ValueError("'smoothing_kernel_size' is required when 'contrast_based' is True")
        
        return self

    @field_validator('smoothing_kernel_size')
    @classmethod
    def must_be_odd(cls, v):
        if v % 2 == 0:
            raise ValueError('smoothing_kernel_size must be an odd integer')
        return v

class AdvancedEdgeDetectionOperation(BaseModel):
    operator: Literal['homogeneity', 'difference', 'gaussian_1', 'gaussian_2', 'variance', 'range']
    contrast_based: bool
    smoothing_kernel_size: Optional[int] = Field(None, ge=3, le=999)
    thresholding: Optional[bool] = None
    threshold: Optional[int] = Field(None,ge=0, le=255)
    kernel_size: Optional[int] = Field(None, ge=3, le=999)

    @model_validator(mode='after')
    def check_threshold_and_kernel_size(self):
        if self.contrast_based:
            if self.smoothing_kernel_size is None:
                raise ValueError("'smoothing_kernel_size' is required when 'contrast_based' is True")
        
        if self.thresholding: 
            if self.threshold is None:
                raise ValueError(f"'threshold' is required for operator '{self.operator}' when 'thresholding' is True")
        
        if self.operator in ['homogeneity', 'difference']:
            if self.threshold is None:
                raise ValueError(f"'threshold' is required for operator '{self.operator}'")
            
            if self.thresholding:
                raise ValueError(f"Thresholding is already applied for operator '{self.operator}'")
            
            if self.contrast_based:
                raise ValueError(f"Cannot apply contrast-based edge detection to '{self.operator}'")
        
        if self.operator in ['variance', 'range']:
            if self.kernel_size is None:
                raise ValueError(f"'kernel_size' is required for operator '{self.operator}'")
        
        if self.operator == 'difference' and self.kernel_size != 3:
            raise ValueError(f"'kernel_size' must be 3 for operator '{self.operator}'")
        
        return self
    
    @field_validator('smoothing_kernel_size', 'kernel_size')
    @classmethod
    def must_be_odd(cls, v):
        if v % 2 == 0:
            raise ValueError('kernel_size must be an odd integer')
        return v

class FilteringOperation(BaseModel):
    mode: Literal['high', 'low', 'median']
    kernel_size: int = Field(ge=3, le=999)
    sigma: Optional[float] = None

    @model_validator(mode='after')
    def check_sigma(self):
        if self.mode == 'median ' and self.sigma is not None:
            raise ValueError('Median filter does not require a sigma value')
        
        return self

    @field_validator('kernel_size')
    @classmethod
    def must_be_odd(cls, v):
        if v % 2 == 0:
            raise ValueError('kernel_size must be an odd integer')
        return v

class MultiImageOperation(BaseModel):
    images: List[str]
    operation: Literal['add', 'subtract', 'cut_paste']
    src_region: Optional[Tuple[int, int, int, int]] = None
    dest_position: Optional[Tuple[int, int]] = None

    @model_validator(mode='after')
    def check_fields_based_on_operation(self):
        if self.operation in ['add', 'subtract']:
            if len(self.images) < 2:
                raise ValueError(f"Operation '{self.operation}' requires at least two images")
            if self.src_region is not None or self.dest_position is not None:
                raise ValueError(f"Operation '{self.operation}' does not use 'src_region' or 'dest_position'")
        elif self.operation == 'cut_paste':
            if len(self.images) != 2:
                raise ValueError("Operation 'cut_paste' requires exactly two images (source and destination)")
            if self.src_region is None or self.dest_position is None:
                raise ValueError("Operation 'cut_paste' requires 'src_region' and 'dest_position'")
        return self

class SingleImageOperation(BaseModel):
    operation: Literal['rotate', 'flip', 'resize', 'invert']
    angle: Optional[float] = None
    mode: Optional[Literal['horizontal', 'vertical']] = None
    output_size: Optional[Tuple[int, int]] = None

    @field_validator('output_size')
    @classmethod
    def validate_output_size(cls, v):
        if v is not None:
            if not (isinstance(v, tuple) and len(v) == 2):
                raise ValueError("'output_size' must be a tuple of two integers (width, height)")
            if not all(isinstance(dim, int) and dim > 0 for dim in v):
                raise ValueError("'output_size' dimensions must be positive integers")
        return v

    @model_validator(mode='after')
    def check_fields_based_on_operation(self):
        if self.operation == 'rotate':
            if self.angle is None:
                raise ValueError("Operation 'rotate' requires 'angle' parameter")
        elif self.operation == 'flip':
            if self.mode not in ['horizontal', 'vertical']:
                raise ValueError("Operation 'flip' requires 'mode' to be 'horizontal' or 'vertical'")
        elif self.operation == 'resize':
            if self.output_size is None:
                raise ValueError("Operation 'resize' requires 'output_size' parameter")
        elif self.operation == 'invert':
            pass 
        return self

class CreateImageOperation(BaseModel):
    width: int = Field(..., gt=0, description="Width of the image in pixels.")
    height: int = Field(..., gt=0, description="Height of the image in pixels.")
    color: Literal['white', 'black'] = Field(..., description="Background color of the image.")

class HistogramSegmentationOperation(BaseModel):
    mode: Literal['manual', 'peak', 'valley', 'adaptive'] = Field(..., description="Segmentation mode: 'manual', 'peak', 'valley', 'adaptive'")
    value: int = Field(255, ge=3, le=999, description="Pixel value to set for thresholded pixels")
    segment: bool = Field(False, description="Whether to perform region growing")
    hi: int = Field(None, description="High threshold value for 'manual' mode")
    low: int = Field(None, description="Low threshold value for 'manual' mode")

    @model_validator(mode='after')
    def check_fields_based_on_mode(self):
        if self.mode == 'manual':
            if self.hi is None or self.low is None:
                raise ValueError("'hi' and 'lo' must be set for manual mode")

        return self
