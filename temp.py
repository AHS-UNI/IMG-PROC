import numpy as np
import io
from PIL import Image
from numpy.lib.stride_tricks import sliding_window_view
import cv2
from pydantic import BaseModel, Field, model_validator, field_validator
from typing import List, Tuple, Literal, Optional, Union, Any


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
            if thresholding:
                raise ValueError(f"Thresholding is already applied for operator '{operator}'.")
            if contrast_based:
                raise ValueError(f"Cannot apply contrast-based edge detection to '{operator}'.")

        if operator in ['variance', 'range']:
            if kernel_size is None:
                raise ValueError(f"'kernel_size' is required for operator '{operator}'.")
            if kernel_size % 2 == 0:
                raise ValueError('kernel_size must be an odd integer.')

        if operator == 'difference' and kernel_size != 3:
            raise ValueError(f"'kernel_size' must be 3 for operator '{operator}'.")

        return self

def apply_convolution(image_array, kernel, stride=1): # fast convolution using opencv
    if image_array.ndim == 3:
        convolved_image = np.zeros_like(image_array)
        for c in range(image_array.shape[2]):
            convolved_image[:, :, c] = cv2.filter2D(image_array[:, :, c], -1, kernel)
    elif image_array.ndim == 2:
        convolved_image = cv2.filter2D(image_array, -1, kernel)
    else:
        raise ValueError("Input image must be a 2D or 3D numpy array.")

    if stride > 1:
        convolved_image = convolved_image[::stride, ::stride]

    return convolved_image


def apply_advanced_edge_detection(image_bytes: bytes, operation: AdvancedEdgeDetectionOperation) -> Any:
    try:
        supported_operators = (
            'homogeneity', 'difference', 
            'gaussian_1', 'gaussian_2', 
            'variance', 'range'
        )
        operator = operation.operator
        if operator not in supported_operators:
            return {"error": f"Unsupported operator '{operator}' for edge detection"}

        image = Image.open(io.BytesIO(image_bytes)).convert('L')
        image_array = np.array(image)
        height, width = image_array.shape

        edge_image_array = np.zeros((height, width))

        if operator == 'homogeneity':
            threshold = operation.threshold
            window_size = operation.kernel_size if operation.kernel_size is not None else 3
            pad_width = window_size // 2
            padded = padded = np.pad(image_array, pad_width=pad_width, mode='constant', constant_values=0)
            
            windows = sliding_window_view(padded, (window_size, window_size))

            center = image_array
            
            max_diff = np.max(np.abs(windows - center[:, :, np.newaxis, np.newaxis]), axis=(2, 3))

            edge_image_array = np.where(max_diff >= threshold, 255, 0)

        elif operator == 'difference':
            threshold = operation.threshold
            window_size = 3
            pad_width = window_size // 2
            padded = np.pad(image_array, pad_width=pad_width, mode='reflect')
            
            windows = sliding_window_view(padded, (window_size, window_size))

            top_left = windows[:, :, 0, 0]  
            bottom_right = windows[:, :, 2, 2]  
            top_right = windows[:, :, 0, 2] 
            bottom_left = windows[:, :, 2, 0]  
            top_center = windows[:, :, 0, 1]  
            bottom_center = windows[:, :, 2, 1]  
            middle_left = windows[:, :, 1, 0]  
            middle_right = windows[:, :, 1, 2]

            diff1 = np.abs(top_left - bottom_right)
            diff2 = np.abs(top_right - bottom_left)
            diff3 = np.abs(top_center - bottom_center)
            diff4 = np.abs(middle_left - middle_right)

            diffs = np.stack((diff1, diff2, diff3, diff4), axis=2)
            max_diffs = diffs.max(axis=2)
            
            edge_image_array = np.where(max_diffs >= threshold, 255, 0)

        elif operator in ('gaussian_1', 'gaussian_2'):
            kernel = None
            if operator == 'gaussian_1':
                kernel = np.array([
                    [0, 0, -1, -1, -1, 0, 0],
                    [0, -2, -3, -3, -3, -2, 0],
                    [-1, -3, 5, 5, 5, -3, -1],
                    [-1, -3, 5, 16, 5, -3, -1],
                    [-1, -3, 5, 5, 5, -3, -1],
                    [0, -2, -3, -3, -3, -2, 0],
                    [0, 0, -1, -1, -1, 0, 0]
                ])
            elif operator == 'gaussian_2':
                kernel = np.array([
                    [0, 0, 0, -1, -1, -1, 0, 0, 0],
                    [0, -2, -3, -3, -3, -3, -3, -2, 0],
                    [0, -3, -2, -1, -1, -1, -2, -3, 0],
                    [-1, -3, -1, 9, 9, 9, -1, -3, -1],
                    [-1, -3, -1, 9, 19, 9, -1, -3, -1],
                    [-1, -3, -1, 9, 9, 9, -1, -3, -1],
                    [0, -3, -2, -1, -1, -1, -2, -3, 0],
                    [0, -2, -3, -3, -3, -3, -3, -2, 0],
                    [0, 0, 0, -1, -1, -1, 0, 0, 0]
                ])

            convolved_image = apply_convolution(image_array, kernel)
            convolved_abs = np.abs(convolved_image)
            
            edge_image_array = (convolved_abs / convolved_abs.max()) * 255

        elif operator == 'variance':
            threshold = operation.threshold
            kernel_size = operation.kernel_size
            pad_width = kernel_size // 2
            padded = np.pad(image_array, pad_width=pad_width, mode='reflect')
            windows = sliding_window_view(padded, (kernel_size, kernel_size))

            edge_image_array = np.var(windows, axis=(2, 3))

        elif operator == 'range':
            threshold = operation.threshold
            kernel_size = operation.kernel_size
            pad_width = kernel_size // 2
            padded = np.pad(image_array, pad_width=pad_width, mode='reflect')
            windows = sliding_window_view(padded, (kernel_size, kernel_size))
 
            edge_image_array = np.max(windows, axis=(2, 3)) - np.min(windows, axis=(2, 3))
        else:
            return {"error": f"Unhandled operator '{operator}' for edge detection"}

        if operation.contrast_based:
            smoothing_kernel_size = operation.smoothing_kernel_size
            smoothing_kernel = np.ones((smoothing_kernel_size, smoothing_kernel_size)) / (smoothing_kernel_size ** 2)

            smoothed_image = apply_convolution(edge_image_array, smoothing_kernel)
            
            with np.errstate(divide='ignore', invalid='ignore'): # avoid division by 0
                smoothed_image_array = np.divide(edge_image_array, smoothed_image)
                smoothed_image_array = np.nan_to_num(smoothed_image_array, nan=0.0, posinf=0.0, neginf=0.0)
            
            edge_image_array = smoothed_image_array
            
        if operation.thresholding:
            threshold = operation.threshold
            edge_image_array = np.where(edge_image_array >= threshold, 255, 0)

        edge_image = Image.fromarray(np.uint8(edge_image_array), mode='L')
        
        buf = io.BytesIO()
        edge_image.save(buf, format='PNG')
        buf.seek(0)

        return buf
    except Exception as e:
        return {"error": str(e)}  