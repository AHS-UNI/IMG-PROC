from PIL import Image, ExifTags, ImageDraw
import io
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
import cv2
from typing import Any, List, Tuple, Optional
from operations import (
    GrayscaleOperation,
    HalftoningOperation,
    HistogramEqualizationOperation,
    HistogramSmoothingOperation,
    BasicEdgeDetectionOperation,
    AdvancedEdgeDetectionOperation,
    FilteringOperation,
    SingleImageOperation,
    MultiImageOperation,
    CreateImageOperation,
    HistogramSegmentationOperation
)

def get_metadata(image_bytes: bytes, filename: str) -> dict:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        width, height = image.size
        mode = image.mode  # e.g., 'RGB', 'RGBA', 'L' (grayscale)
        img_format = image.format  # e.g., 'JPEG', 'PNG'
        is_compressed = img_format not in ['BMP', 'PPM', 'PGM']  # uncompressed formats
        file_size_kb = round(len(image_bytes) / 1024, 2)  # convert bytes to kilobytes, rounded to 2 decimals
        channels = len(mode)  # number of color channels

        # extract EXIF data if available
        exif_data = {}
        if hasattr(image, '_getexif') and image._getexif():
            exif_raw = image._getexif()
            for tag_id, value in exif_raw.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                exif_data[tag] = value

        metadata = {
            "file_name": filename,
            "format": img_format,
            "compressed": is_compressed,
            "file_size_kilobytes": file_size_kb,
            "width": width,
            "height": height,
            "color_mode": mode,
            "channels": channels,
            "exif_tags": exif_data if exif_data else None,
        }

        return metadata

    except Exception as e:
        return {"error": str(e)}

def calculate_histogram(image_array: np.ndarray) -> Any:
    if image_array.ndim == 2:  # grayscale image
        histogram = np.bincount(image_array.flatten(), minlength=256)
        return histogram
    elif image_array.ndim == 3 and image_array.shape[2] == 3:  # RGB image
        histograms = {}
        color_channels = ('red', 'green', 'blue')
        for i, color in enumerate(color_channels):
            channel = image_array[:, :, i].flatten()
            histograms[color] = np.bincount(channel, minlength=256)
        return histograms
    else:
        raise ValueError("Input image must be either a 2D grayscale or 3D RGB image array.")

# def create_histogram_image(histograms: Any, image_mode: str) -> io.BytesIO:
#     if image_mode == 'L':  # greyscale
#         fig, ax = plt.subplots(figsize=(10, 2))
#         ax.bar(range(256), histograms, color='gray')
#         ax.set_title('Grayscale Histogram')
#         ax.set_xlabel('Pixel Intensity')
#         ax.set_ylabel('Frequency')
#         plt.tight_layout()
#     elif image_mode == 'RGB':
#         fig, axes = plt.subplots(3, 1, figsize=(10, 6))
#         color_channels = ('Red', 'Green', 'Blue')
#         colors = ('red', 'green', 'blue')
#         for i, (ax, color, channel_name) in enumerate(zip(axes, colors, color_channels)):
#             ax.bar(range(256), histograms[color], color=color)
#             ax.set_title(f'{channel_name} Channel Histogram')
#             ax.set_xlabel('Pixel Intensity')
#             ax.set_ylabel('Frequency')
#             plt.tight_layout()
#     else:
#         return {"error": "Unsupported image mode for histogram generation."}
    
#     canvas = FigureCanvas(fig)

#     buf = io.BytesIO()
#     canvas.print_png(buf)
#     plt.close(fig)
#     buf.seek(0)
#     return buf

def create_histogram_image(histograms: Any, image_mode: str) -> io.BytesIO:
    if image_mode == 'L':
        width = 256
        height = 100
        hist_image = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(hist_image)
        max_freq = max(histograms)
        for x in range(256):
            y = histograms[x]
            draw.line([(x, height), (x, height - int((y / max_freq) * height))], fill='gray')
    elif image_mode == 'RGB':
        width = 256
        height = 300
        hist_image = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(hist_image)
        color_channels = ('red', 'green', 'blue')
        colors = ('red', 'green', 'blue')
        max_freq = max([max(histograms[color]) for color in colors])
        for i, color in enumerate(colors):
            for x in range(256):
                y = histograms[color][x]
                draw.line([(x, height - i*100), (x, height - i*100 - int((y / max_freq) * 100))], fill=color)
    else:
        return {"error": "Unsupported image mode for histogram generation."}
    
    buf = io.BytesIO()
    hist_image.save(buf, format='PNG')
    buf.seek(0)
    return buf

def get_histograms(image_bytes: bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        if image.mode not in ('L', 'RGB'):
            if image.mode in ('I', 'F'):
                # Normalize and convert to grayscale
                image = image.point(lambda x: x * (255 / (image.getextrema()[1] or 1)))
                image = image.convert('L')
            else:
                # Convert to RGB
                image = image.convert('RGB')
        
        image_array = np.array(image)
        histograms = calculate_histogram(image_array)
        
        if image.mode == 'L':
            image_mode = 'L'
        elif image.mode == 'RGB':
            image_mode = 'RGB'
        else:
            return {"error": "Unsupported image mode for histogram generation."}

        histogram_image = create_histogram_image(histograms, image_mode)
        return histogram_image

    except Exception as e:
        return {"error": str(e)}

def to_png_bytes(image_bytes: bytes) -> Any: 
    try:
        image = Image.open(io.BytesIO(image_bytes))
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        buf.seek(0)
        return buf
    except Exception as e:
        return {"error": str(e)}

def apply_grayscale(image_bytes: bytes, operation: GrayscaleOperation) -> Any:
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        image_array = np.array(image)

        if operation.mode == 'luminosity':
            luminosity_weights = np.array([0.21, 0.72, 0.07])
            gray_image_array = image_array.dot(luminosity_weights)
        elif operation.mode == 'lightness':
            max_rgb = image_array.max(axis=2)
            min_rgb = image_array.min(axis=2)
            gray_image_array = ((max_rgb + min_rgb) / 2)
        else:
            return {"error": "Invalid mode specified."}

        greyscale_image = Image.fromarray(np.uint8(gray_image_array), mode='L')

        buf = io.BytesIO()
        greyscale_image.save(buf, format='PNG')
        buf.seek(0)
        return buf

    except Exception as e:
        return {"error": str(e)}

def apply_halftoning(image_bytes: bytes, operation: HalftoningOperation) -> Any:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        mode = operation.mode
        method = operation.method
        threshold = operation.threshold
        
        if mode == 'grayscale':
            image = image.convert('L')
            if method == 'thresholding':
                halftoned_image_array = halftone_greyscale_thresholding(image, threshold)
            elif method == 'error_diffusion':
                halftoned_image_array = halftone_greyscale_error_diffusion(image, threshold)
            else:
                return {"error": f"Unsupported halftoning method '{method}' for mode 'grayscale'."}
            
            halftoned_image = Image.fromarray(np.uint8(halftoned_image_array), mode='L')
        elif mode == 'rgb':
            image = image.convert('RGB')
            if method == 'thresholding':
                halftoned_image_array = halftone_rgb_thresholding(image, threshold)
            elif method == 'error_diffusion':
                halftoned_image_array = halftone_rgb_error_diffusion(image, threshold)
            else:
                return {"error": f"Unsupported halftoning method '{method}' for mode 'RGB'."}
            
            halftoned_image = Image.fromarray(np.uint8(halftoned_image_array), mode='RGB')
        else:
            return {"error": f"Unsupported halftoning mode '{mode}'."}
        
        buf = io.BytesIO()
        halftoned_image.save(buf, format='PNG')
        buf.seek(0)
        return buf

    except Exception as e:
        return {"error": str(e)}

def halftone_greyscale_thresholding(image: Image.Image, threshold: int) -> Image.Image:
    image_array = np.array(image)
    halftoned_image_array = np.where(image_array > threshold, 255, 0)
    
    return halftoned_image_array

def halftone_greyscale_error_diffusion(image, threshold):
    image_array = np.array(image, dtype=float)
    height, width = image_array.shape

    # Floyd-Steinberg kernel
    error_diffusion = [
        (0, 1, 7 / 16),
        (1, -1, 3 / 16),
        (1, 0, 5 / 16),
        (1, 1, 1 / 16)
    ]

    for y in range(height):
        for x in range(width):
            old_pixel = image_array[y, x]
            new_pixel = 255 if old_pixel > threshold else 0
            image_array[y, x] = new_pixel
            quant_error = old_pixel - new_pixel

            for dy, dx, coefficient in error_diffusion:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        image_array[ny, nx] += quant_error * coefficient

    halftoned_image_array = np.clip(image_array, 0, 255)
    
    return halftoned_image_array

def halftone_rgb_thresholding(image: Image.Image, threshold: Tuple[int, int, int]) -> Image.Image:
    image_array = np.array(image)

    threshold_r, threshold_g, threshold_b = threshold
    
    halftoned_image_array = np.zeros_like(image_array)
    halftoned_image_array[:, :, 0] = np.where(image_array[:, :, 0] > threshold_r, 255, 0)
    halftoned_image_array[:, :, 1] = np.where(image_array[:, :, 1] > threshold_g, 255, 0)
    halftoned_image_array[:, :, 2] = np.where(image_array[:, :, 2] > threshold_b, 255, 0)
    
    return halftoned_image_array

def halftone_rgb_error_diffusion(image: Image.Image, threshold: Tuple[int, int, int]) -> Image.Image:
    image_array = np.array(image, dtype=float)
    height, width, channels = image_array.shape
    
    threshold_r, threshold_g, threshold_b = threshold
    
    # Floyd-Steinberg kernel
    error_diffusion = [
        (0, 1, 7 / 16),
        (1, -1, 3 / 16),
        (1, 0, 5 / 16),
        (1, 1, 1 / 16)
    ]
    
    for y in range(height):
        for x in range(width):
            for c in range(channels):
                old_pixel = image_array[y, x, c]
                current_threshold = [threshold_r, threshold_g, threshold_b][c]
                new_pixel = 255 if old_pixel > current_threshold else 0
                image_array[y, x, c] = new_pixel
                quant_error = old_pixel - new_pixel

                for dy, dx, coefficient in error_diffusion:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        image_array[ny, nx, c] += quant_error * coefficient

    halftoned_image_array = np.clip(image_array, 0, 255)
    
    return halftoned_image_array

def apply_histogram_smoothing(image_bytes: bytes, operation: HistogramSmoothingOperation) -> Any:
    try:
        image = Image.open(io.BytesIO(image_bytes))

        kernel_size = operation.kernel_size

        if operation.mode == 'grayscale':
            image = image.convert('L') 
            image_array = np.array(image)

            image_histogram = calculate_histogram(image_array)

            smoothed_histogram = smooth_histogram(image_histogram, kernel_size)
            smoothed_image_array = map_hist_to_image(image_array, smoothed_histogram)

            smoothed_image = Image.fromarray(np.uint8(smoothed_image_array), mode='L')
        elif operation.mode == 'rgb':
            image = image.convert('RGB')
            image_array = np.array(image)

            smoothed_image_array = np.zeros_like(image_array)

            for i in range(3):
                channel_array = image_array[:, :, i]
                source_histogram = calculate_histogram(channel_array)

                smoothed_histogram = smooth_histogram(source_histogram, kernel_size)

                smoothed_channel_array = map_hist_to_image(channel_array, smoothed_histogram)

                smoothed_image_array[:, :, i] = smoothed_channel_array

            smoothed_image = Image.fromarray(smoothed_image_array, mode='RGB')

        else:
            raise ValueError(f"Unsupported mode '{operation.mode}'. Choose 'grayscale' or 'rgb'.")

        buf = io.BytesIO()
        smoothed_image.save(buf, format='PNG')
        buf.seek(0)

        return buf

    except Exception as e:
        return {"error": str(e)}

def smooth_histogram(histogram: np.ndarray, kernel_size):
    kernel = np.ones(kernel_size) / kernel_size
    histogram_smooth = np.convolve(histogram, kernel, mode='same')
    histogram_smooth = np.round(histogram_smooth).astype(int)
    return histogram_smooth

def map_hist_to_image(image_array: np.ndarray, target_histogram: np.ndarray):
    source_histogram = calculate_histogram(image_array)
    
    cdf_source = np.cumsum(source_histogram).astype(np.float64)
    cdf_source /= cdf_source[-1]

    cdf_target = np.cumsum(target_histogram).astype(np.float64)
    cdf_target /= cdf_target[-1]

    mapping = np.interp(cdf_source, cdf_target, np.arange(256))

    for src_value in range(256):
        diff = np.abs(cdf_source[src_value] - cdf_target)
        mapping[src_value] = np.argmin(diff)

    mapping = np.interp(cdf_source, cdf_target, np.arange(256))

    mapped_image_array = mapping[image_array]

    return mapped_image_array

def apply_histogram_equalization(image_bytes: bytes, operation: HistogramEqualizationOperation) -> Any:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        if operation.mode == 'grayscale':
            image = image.convert('L')
            image_array = np.array(image)
            equalized_image_array = equalize_channel(image_array)
            equalized_image = Image.fromarray(np.uint8(equalized_image_array), mode='L')
        elif operation.mode == 'rgb':
            # convert to YCbCr color space for luminance handling
            image = image.convert('YCbCr')
            image_array = np.array(image)

            Y_channel = image_array[:, :, 0]  # channel to equalize
            Cb_channel = image_array[:, :, 1]  
            Cr_channel = image_array[:, :, 2]

            equalized_Y_channel = equalize_channel(Y_channel)
            equalized_image_array = np.stack((equalized_Y_channel, Cb_channel, Cr_channel), axis=2)
            
            equalized_image = Image.fromarray(np.uint8(equalized_image_array), mode='YCbCr')
            equalized_image = equalized_image.convert('RGB')
        else:
            return {"error": f"Unsupported equalization mode '{operation.mode}'."}
        
        buf = io.BytesIO()
        equalized_image.save(buf, format='PNG')
        buf.seek(0)
        return buf

    except Exception as e:
        return {"error": str(e)}
    
def equalize_channel(channel_array: np.ndarray) -> np.ndarray:
    histogram = calculate_histogram(channel_array)

    cdf = histogram.cumsum()
    cdf_normalized = (cdf - cdf.min()) * 255 / (cdf.max() - cdf.min())
    cdf_normalized = cdf_normalized.astype(np.uint8)

    equalized_channel_array = cdf_normalized[channel_array]

    return equalized_channel_array

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

def apply_basic_edge_detection(image_bytes: bytes, operation: BasicEdgeDetectionOperation) -> Any:
    try:
        supported_operators = (
            'roberts', 'sobel', 'prewitt', 
            'kirsch', 'robinson', 
            'laplacian_1', 'laplacian_2'
        )
        operator = operation.operator
        if operator not in supported_operators:
            return {"error": f"Unsupported operator '{operator}' for edge detection"}
        
        gradient_based = ('roberts', 'sobel', 'prewitt')
        compass_based = ('kirsch', 'robinson')
        laplacian_based = ('laplacian_1', 'laplacian_2')

        image = Image.open(io.BytesIO(image_bytes)).convert('L')
        image_array = np.array(image)
        height, width = image_array.shape
        
        edge_image_array = np.zeros((height, width))
        
        if operator in gradient_based:
            # gradient-based kernels
            if operator == 'roberts':
                Gx = np.array([[1, 0],
                               [0, -1]])
                Gy = np.array([[0, 1],
                               [-1, 0]])
            elif operator == 'sobel':
                Gx = np.array([[-1, 0, 1],
                               [-2, 0, 2],
                               [-1, 0, 1]])
                Gy = np.array([[1, 2, 1],
                               [0, 0, 0],
                               [-1, -2, -1]])
            elif operator == 'prewitt':
                Gx = np.array([[-1, 0, 1],
                               [-1, 0, 1],
                               [-1, 0, 1]])
                Gy = np.array([[1, 1, 1],
                               [0, 0, 0],
                               [-1, -1, -1]])

            grad_x = apply_convolution(image_array, Gx, stride=1)
            grad_y = apply_convolution(image_array, Gy, stride=1)

            gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
            gradient_magnitude = (gradient_magnitude / gradient_magnitude.max()) * 255
            edge_image_array = gradient_magnitude

        elif operator in compass_based:
            # compass-based kernels
            if operator == 'kirsch':
                kirsch_kernels = [
                    np.array([[-3, -3,  5],
                              [-3,  0,  5],
                              [-3, -3,  5]]),
                    np.array([[-3,  5,  5],
                              [-3,  0,  5],
                              [-3, -3, -3]]),
                    np.array([[ 5,  5,  5],
                              [-3,  0, -3],
                              [-3, -3, -3]]),
                    np.array([[ 5,  5, -3],
                              [ 5,  0, -3],
                              [-3, -3, -3]]),
                    np.array([[ 5, -3, -3],
                              [ 5,  0, -3],
                              [ 5, -3, -3]]),
                    np.array([[-3, -3, -3],
                              [ 5,  0, -3],
                              [ 5,  5, -3]]),
                    np.array([[-3, -3, -3],
                              [-3,  0, -3],
                              [ 5,  5,  5]]),
                    np.array([[-3, -3, -3],
                              [-3,  0,  5],
                              [-3,  5,  5]])
                ]
            elif operator == 'robinson':
                robinson_kernels = [
                    np.array([[-1,  0,  1],
                              [-2,  0,  2],
                              [-1,  0,  1]]),
                    np.array([[ 0,  1,  2],
                              [-1,  0,  1],
                              [-2, -1,  0]]),
                    np.array([[ 1,  2,  1],
                              [ 0,  0,  0],
                              [-1, -2, -1]]),
                    np.array([[ 2,  1,  0],
                              [ 1,  0, -1],
                              [ 0, -1, -2]]),
                    np.array([[ 1,  0, -1],
                              [ 2,  0, -2],
                              [ 1,  0, -1]]),
                    np.array([[ 0, -1, -2],
                              [ 1,  0, -1],
                              [ 2,  1,  0]]),
                    np.array([[-1, -2, -1],
                              [ 0,  0,  0],
                              [ 1,  2,  1]]),
                    np.array([[-2, -1,  0],
                              [-1,  0,  1],
                              [ 0,  1,  2]])
                ]

            if operator == 'kirsch':
                kernels = kirsch_kernels
            elif operator == 'robinson':
                kernels = robinson_kernels

            responses = []
            for kernel in kernels:
                response = apply_convolution(image_array, kernel, stride=1)
                responses.append(response)

            stacked_responses = np.stack(responses, axis=0)
            max_response = np.max(stacked_responses, axis=0)

            max_response = (max_response / np.max(max_response)) * 255
            edge_image_array = max_response
    
        elif operator in laplacian_based:
            if operator == 'laplacian_1':
                laplacian_kernel = np.array([[ 0, -1,  0],
                                             [-1,  4, -1],
                                             [ 0, -1,  0]])
            elif operator == 'laplacian_2':
                laplacian_kernel = np.array([[-1, -1, -1],
                                             [-1,  8, -1],
                                             [-1, -1, -1]])

            laplacian_response = apply_convolution(image_array, laplacian_kernel, stride=1)

            laplacian_response = np.abs(laplacian_response)

            laplacian_response = (laplacian_response / laplacian_response.max()) * 255
            edge_image_array = laplacian_response
        
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
    
def apply_filtering(image_bytes: bytes, operation: FilteringOperation) -> Any:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image_array = np.array(image)
        
        kernel_size = operation.kernel_size
        sigma = operation.sigma
        mode = operation.mode

        if mode == 'low':
            kernel = generate_gaussian_kernel(kernel_size, sigma)
            filtered_image_array = apply_convolution(image_array, kernel)
        elif mode == 'high':
            kernel = generate_log_kernel(kernel_size, sigma)
            filtered_image_array = apply_convolution(image_array, kernel)
        elif mode == 'median':
            pad_size = kernel_size // 2
            padded_array = np.pad(image_array, pad_size, mode='constant', constant_values=0)

            windows = sliding_window_view(padded_array, (kernel_size, kernel_size))
            filtered_image_array = np.median(windows, axis=(-2, -1))
        else:
            raise ValueError(f"Unsupported mode: {mode}. Supported modes are 'low', 'high', 'median'.")

        filtered_image = Image.fromarray(np.uint8(filtered_image_array))

        buf = io.BytesIO()
        filtered_image.save(buf, format='PNG')
        buf.seek(0)

        return buf
    except Exception as e:
        print(f"Error: {e}")
        return None
    
def generate_gaussian_kernel(size, sigma=None):
    if sigma is None:
        sigma = size / 6.0 

    ax = np.linspace(-(size // 2), size // 2, size)
    xx, yy = np.meshgrid(ax, ax)
    kernel = np.exp(-(xx**2 + yy**2) / (2. * sigma**2))
    kernel /= np.sum(kernel)
    return kernel

def generate_log_kernel(size, sigma=None):
    if sigma is None:
        sigma = size / 6.0

    ax = np.arange(-size // 2 + 1., size // 2 + 1.)
    xx, yy = np.meshgrid(ax, ax)
    xy_squared = xx**2 + yy**2

    normalization = -1 / (np.pi * sigma**4)
    laplacian = (1 - (xy_squared) / (2 * sigma**2))
    gaussian = np.exp(-xy_squared / (2 * sigma**2))

    kernel = normalization * laplacian * gaussian
    kernel -= kernel.mean()
    return kernel

def apply_single_image_operation(image_bytes: bytes, operation: SingleImageOperation) -> Any:
    image = Image.open(io.BytesIO(image_bytes)).convert('RGB') # for simplicity all images converted to RGB
    image_array = np.array(image)
    
    if operation.operation == 'rotate':
        angle = operation.angle
        result_image_array = rotate_image(image_array, angle)
    elif operation.operation == 'flip':
        mode = operation.mode
        result_image_array = flip_image(image_array, mode)
    elif operation.operation == 'resize':
        output_size = operation.output_size
        result_image_array = resize_image(image_array, output_size)
    elif operation.operation == 'invert':
        result_image_array = invert_image(image_array)
    else:
        raise ValueError(f"Unsupported operation: {operation.operation}")

    result_image = Image.fromarray(np.uint8(result_image_array), mode='RGB')

    buf = io.BytesIO()
    result_image.save(buf, format='PNG')
    buf.seek(0)

    return buf

def rotate_image(image_array: np.ndarray, angle: float) -> np.ndarray:
    theta = np.radians(angle)
    cos_theta, sin_theta = np.cos(theta), np.sin(theta)

    height, width, channels = image_array.shape
    rotated_image_array = np.zeros_like(image_array)

    y_indices, x_indices = np.indices((height, width))
    x_dest = x_indices - width / 2
    y_dest = y_indices - height / 2

    x_src = cos_theta * x_dest + sin_theta * y_dest + width / 2
    y_src = -sin_theta * x_dest + cos_theta * y_dest + height / 2

    mask = (x_src >= 0) & (x_src < width - 1) & (y_src >= 0) & (y_src < height - 1) # mask of valid coords

    x_src_valid = x_src[mask]
    y_src_valid = y_src[mask]

    x0 = np.floor(x_src_valid).astype(int)
    y0 = np.floor(y_src_valid).astype(int)

    x_frac = x_src_valid - x0
    y_frac = y_src_valid - y0

    wa = (1 - x_frac) * (1 - y_frac)
    wb = x_frac * (1 - y_frac)
    wc = (1 - x_frac) * y_frac
    wd = x_frac * y_frac

    wa = wa[:, np.newaxis]
    wb = wb[:, np.newaxis]
    wc = wc[:, np.newaxis]
    wd = wd[:, np.newaxis]

    Ia = image_array[y0, x0]
    Ib = image_array[y0, x0 + 1]
    Ic = image_array[y0 + 1, x0]
    Id = image_array[y0 + 1, x0 + 1]

    rotated_pixels = wa * Ia + wb * Ib + wc * Ic + wd * Id

    rotated_image_array[y_indices[mask], x_indices[mask]] = rotated_pixels
    rotated_image_array = np.clip(rotated_image_array, 0, 255)

    return rotated_image_array

def resize_image(image_array: np.ndarray, output_size: Tuple[int, int]) -> np.ndarray:
    src_height, src_width, channels = image_array.shape
    dst_width, dst_height = output_size

    y_dst, x_dst = np.indices((dst_height, dst_width))

    x_src = (x_dst + 0.5) * (src_width / dst_width) - 0.5
    y_src = (y_dst + 0.5) * (src_height / dst_height) - 0.5

    x_src = np.clip(x_src, 0, src_width - 1.001)
    y_src = np.clip(y_src, 0, src_height - 1.001)

    x0 = x_src.astype(int)
    y0 = y_src.astype(int)
    x_frac = x_src - x0
    y_frac = y_src - y0

    x1 = x0 + 1
    y1 = y0 + 1
    x1 = np.clip(x1, 0, src_width - 1)
    y1 = np.clip(y1, 0, src_height - 1)

    wa = (1 - x_frac) * (1 - y_frac)
    wb = x_frac * (1 - y_frac)
    wc = (1 - x_frac) * y_frac
    wd = x_frac * y_frac

    wa = wa[:, :, np.newaxis]
    wb = wb[:, :, np.newaxis]
    wc = wc[:, :, np.newaxis]
    wd = wd[:, :, np.newaxis]

    Ia = image_array[y0, x0]
    Ib = image_array[y0, x1]
    Ic = image_array[y1, x0]
    Id = image_array[y1, x1]

    resized_image_array = wa * Ia + wb * Ib + wc * Ic + wd * Id
    resized_image_array = np.clip(resized_image_array, 0, 255)

    return resized_image_array

def flip_image(image_array: np.ndarray, mode: str) -> np.ndarray:
    """
    Flips the image horizontally or vertically.
    """
    if mode == 'horizontal':
        return image_array[:, ::-1, :]
    elif mode == 'vertical':
        return image_array[::-1, :, :]
    
def invert_image(image_array: np.ndarray) -> np.ndarray:
    return 255 - image_array

def apply_multi_image_operation(operation: MultiImageOperation) -> Any:
    try:
        image_arrays = []
        for idx, img_bytes in enumerate(operation.images):
            try:
                img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                img_array = np.array(img)
                image_arrays.append(img_array)
            except Exception as e:
                return {"error": f"Error loading image {idx + 1}: {str(e)}"}
        
        base_shape = image_arrays[0].shape

        if operation.operation == 'add':
            for idx, img_array in enumerate(image_arrays):
                if img_array.shape != base_shape:
                    return {"error": f"All images must have the same dimensions for 'add' operation. Image {idx + 1} has shape {img_array.shape}, expected {base_shape}."}
            
            result_array = np.zeros_like(image_arrays[0], dtype=np.float32)
            for img in image_arrays:
                result_array += img.astype(np.float32)

        elif operation.operation == 'subtract':
            if img_array.shape != base_shape:
                    return {"error": f"All images must have the same dimensions for 'add' operation. Image {idx + 1} has shape {img_array.shape}, expected {base_shape}."}
            
            result_array = image_arrays[0].astype(np.float32)

            for img in image_arrays[1:]:
                result_array -= img.astype(np.float32)

        elif operation.operation == 'cut_paste':
            source_array = image_arrays[0]
            dest_array = image_arrays[1]
            src_region = operation.src_region
            dest_position = operation.dest_position

            x1, y1, x2, y2 = src_region
            dest_x, dest_y = dest_position

            src_height, src_width, _ = source_array.shape
            if not (0 <= x1 < x2 <= src_width and 0 <= y1 < y2 <= src_height):
                raise ValueError("Invalid src_region coordinates.")

            region = source_array[y1:y2, x1:x2].copy()

            region_height, region_width, _ = region.shape

            dest_height, dest_width, _ = dest_array.shape
            if not (0 <= dest_x < dest_width and 0 <= dest_y < dest_height):
                raise ValueError("Invalid dest_position coordinates.")

            end_x = min(dest_x + region_width, dest_width)
            end_y = min(dest_y + region_height, dest_height)

            paste_width = end_x - dest_x
            paste_height = end_y - dest_y

            if paste_width <= 0 or paste_height <= 0:
                raise ValueError("Destination position is out of bounds for the region to paste.")

            dest_array[dest_y:end_y, dest_x:end_x] = region[0:paste_height, 0:paste_width]

            result_array = dest_array

        result_array = np.clip(result_array, 0, 255)
        result_image = Image.fromarray(np.uint8(result_array), mode='RGB')

        buf = io.BytesIO()
        result_image.save(buf, format='PNG')
        buf.seek(0)

        return buf
    except Exception as e:
        return {"error": str(e)}
    
def create_image(operation: CreateImageOperation) -> Any:
    try:
        width = operation.width
        height = operation.height
        color = operation.color

        color_map = {
            'white': (255),
            'black': (0)
        }
        
        if color not in color_map:
            return {"error": f"Unsupported color '{color}'. Choose 'white' or 'black'."}

        image_array = np.full((height, width), color_map[color], dtype=np.uint8)

        image = Image.fromarray(image_array, mode='L')

        buf = io.BytesIO()
        image.save(buf, format='PNG')
        buf.seek(0)
        
        return buf
    
    except Exception as e:
        return {"error": str(e)}
    
def apply_histogram_based_segmentation(image_bytes: bytes, operation: HistogramSegmentationOperation) -> Any:
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert('L')
        image_array = np.array(image)

        hi = None
        low = None

        histogram = calculate_histogram(image_array)

        histogram_smooth = smooth_histogram(histogram, kernel_size=5)

        if operation.mode == 'manual':
            hi = operation.hi
            low = operation.low
        elif operation.mode == 'peak':
            peaks = find_peaks(histogram_smooth)
            peak1, peak2 = peaks[:2]
            hi, low = peaks_high_low(histogram, peak1, peak2)
        elif operation.mode == 'valley':
            peaks = find_peaks(histogram_smooth)
            valleys = find_valleys(histogram_smooth, peaks)
            valley_point = valleys[0] if valleys else (peaks[0] + peaks[1]) // 2
            hi, low = valley_high_low(histogram, valley_point)
        elif operation.mode == 'adaptive':
            peaks = find_peaks(histogram_smooth)
            peak1, peak2 = peaks[:2]
            hi, low = peaks_high_low(histogram, peak1, peak2)
            thresholded_image = threshold_image_array(image_array, hi, low, operation.value)
            object_mean, background_mean = compute_means(image_array, thresholded_image, operation.value)
            hi, low = peaks_high_low(histogram, object_mean, background_mean)
        else:
            return {"error": "Invalid mode specified."}
        
        thresholded_image = threshold_image_array(image_array, hi, low, operation.value)

        if operation.segment:
            labeled_image = label_regions(thresholded_image, operation.value)
            max_label = labeled_image.max()
            if max_label > 0:
                labeled_image = (labeled_image * (255 / max_label))
        else:
            labeled_image = thresholded_image
        
        result_image = Image.fromarray(np.uint8(labeled_image))
        buf = io.BytesIO()
        result_image.save(buf, format='PNG')
        buf.seek(0)

        return buf
    except Exception as e:
        return {"error": str(e)}

def find_peaks(histogram, num_peaks=5):
    peaks = []
    idxtopeak = [None] * len(histogram)
    indices = sorted(range(len(histogram)), key=lambda i: histogram[i], reverse=True)

    for idx in indices:
        lftdone = idx > 0 and idxtopeak[idx - 1] is not None
        rgtdone = idx < len(histogram) - 1 and idxtopeak[idx + 1] is not None
        il = idxtopeak[idx - 1] if lftdone else None
        ir = idxtopeak[idx + 1] if rgtdone else None

        if not lftdone and not rgtdone:
            # New peak born
            peak = {'born': idx, 'left': idx, 'right': idx, 'died': None}
            peaks.append(peak)
            idxtopeak[idx] = len(peaks) - 1
        elif lftdone and not rgtdone:
            # Extend left peak to the right
            peak_id = il
            peaks[peak_id]['right'] = idx
            idxtopeak[idx] = peak_id
        elif not lftdone and rgtdone:
            # Extend right peak to the left
            peak_id = ir
            peaks[peak_id]['left'] = idx
            idxtopeak[idx] = peak_id
        elif lftdone and rgtdone and il != ir:
            # Merge left and right peaks
            left_peak = peaks[il]
            right_peak = peaks[ir]
            left_persistence = histogram[left_peak['born']] - histogram[idx]
            right_persistence = histogram[right_peak['born']] - histogram[idx]
            if left_persistence >= right_persistence:
                # Merge right peak into left peak
                right_peak['died'] = idx
                left_peak['right'] = right_peak['right']
                # Update idxtopeak mapping
                for i in range(left_peak['left'], left_peak['right'] + 1):
                    idxtopeak[i] = il
            else:
                # Merge left peak into right peak
                left_peak['died'] = idx
                right_peak['left'] = left_peak['left']
                # Update idxtopeak mapping
                for i in range(right_peak['left'], right_peak['right'] + 1):
                    idxtopeak[i] = ir
        elif lftdone and rgtdone and il == ir:
            # Both neighbors belong to the same peak
            idxtopeak[idx] = il

    # Calculate persistence
    peak_persistence = []
    for peak in peaks:
        born = peak['born']
        died = peak['died']
        persistence = histogram[born] - (histogram[died] if died is not None else 0)
        peak_persistence.append({'index': born, 'persistence': persistence})

    # Sort peaks by persistence
    sorted_peaks = sorted(peak_persistence, key=lambda x: x['persistence'], reverse=True)
    top_peaks = [peak['index'] for peak in sorted_peaks[:num_peaks]]
    return top_peaks

def peaks_high_low(histogram, peak1, peak2):
    if peak1 > peak2:
        mid_point = ((peak1 - peak2) // 2) + peak2
    else:
        mid_point = ((peak2 - peak1) // 2) + peak1
    sum1 = np.sum(histogram[:mid_point])
    sum2 = np.sum(histogram[mid_point:])
    if sum1 >= sum2:  # lower half has more pixels
        low = mid_point
        hi = 255
    else:  # ligher half has more pixels
        low = 0
        hi = mid_point
    return hi, low

def find_valleys(histogram, peaks, num_valleys=5):
    inverted_histogram = -histogram
    valleys = []
    idxtovalley = [None] * len(histogram)
    indices = sorted(range(len(histogram)), key=lambda i: inverted_histogram[i], reverse=True)

    for idx in indices:
        lftdone = idx > 0 and idxtovalley[idx - 1] is not None
        rgtdone = idx < len(histogram) - 1 and idxtovalley[idx + 1] is not None
        il = idxtovalley[idx - 1] if lftdone else None
        ir = idxtovalley[idx + 1] if rgtdone else None

        if not lftdone and not rgtdone:
            # New valley born
            valley = {'born': idx, 'left': idx, 'right': idx, 'died': None}
            valleys.append(valley)
            idxtovalley[idx] = len(valleys) - 1
        elif lftdone and not rgtdone:
            # Extend left valley to the right
            valley_id = il
            valleys[valley_id]['right'] = idx
            idxtovalley[idx] = valley_id
        elif not lftdone and rgtdone:
            # Extend right valley to the left
            valley_id = ir
            valleys[valley_id]['left'] = idx
            idxtovalley[idx] = valley_id
        elif lftdone and rgtdone and il != ir:
            # Merge left and right valleys
            left_valley = valleys[il]
            right_valley = valleys[ir]
            left_persistence = inverted_histogram[left_valley['born']] - inverted_histogram[idx]
            right_persistence = inverted_histogram[right_valley['born']] - inverted_histogram[idx]
            if left_persistence >= right_persistence:
                # Merge right valley into left valley
                right_valley['died'] = idx
                left_valley['right'] = right_valley['right']
                # Update idxtovalley mapping
                for i in range(left_valley['left'], left_valley['right'] + 1):
                    idxtovalley[i] = il
            else:
                # Merge left valley into right valley
                left_valley['died'] = idx
                right_valley['left'] = left_valley['left']
                # Update idxtovalley mapping
                for i in range(right_valley['left'], right_valley['right'] + 1):
                    idxtovalley[i] = ir
        elif lftdone and rgtdone and il == ir:
            # Both neighbors belong to the same valley
            idxtovalley[idx] = il

    # Calculate persistence
    valley_persistence = []
    for valley in valleys:
        born = valley['born']
        died = valley['died']
        persistence = inverted_histogram[born] - (inverted_histogram[died] if died is not None else 0)
        valley_persistence.append({'index': born, 'persistence': persistence})

    # Sort valleys by persistence
    sorted_valleys = sorted(valley_persistence, key=lambda x: x['persistence'], reverse=True)
    top_valleys = [valley['index'] for valley in sorted_valleys[:num_valleys]]

    # Filter valleys between the peaks
    filtered_valleys = [v for v in top_valleys if min(peaks) < v < max(peaks)]
    return filtered_valleys

def valley_high_low(histogram, valley_point):
    sum1 = np.sum(histogram[:valley_point])
    sum2 = np.sum(histogram[valley_point:])
    if sum1 >= sum2:
        low = valley_point
        hi = 255
    else:
        low = 0
        hi = valley_point
    return hi, low

def threshold_image_array(image_array, hi, low, value):
    thresholded_image = np.where((image_array >= low) & (image_array <= hi), value, 0)
    return thresholded_image

def compute_means(image_array, thresholded_image, value):
    object_pixels = image_array[thresholded_image == value]
    background_pixels = image_array[thresholded_image != value]
    if len(object_pixels) == 0 or len(background_pixels) == 0:
        object_mean = background_mean = 0
    else:
        object_mean = np.mean(object_pixels)
        background_mean = np.mean(background_pixels)
    return int(object_mean), int(background_mean)

def label_regions(thresholded_image, value):
    labeled_image = np.zeros_like(thresholded_image, dtype=int)
    label = 1
    rows, cols = thresholded_image.shape

    mask = (thresholded_image == value)

    neighbor_offsets = [(-1, -1), (-1, 0), (-1, 1),
                        ( 0, -1),         ( 0, 1),
                        ( 1, -1), ( 1, 0), ( 1, 1)]

    for i in range(rows):
        for j in range(cols):
            if mask[i, j]:

                stack = [(i, j)]
                mask[i, j] = False
                labeled_image[i, j] = label
                while stack:
                    x, y = stack.pop()

                    for dx, dy in neighbor_offsets:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < rows and 0 <= ny < cols:
                            if mask[nx, ny]:
                                mask[nx, ny] = False
                                labeled_image[nx, ny] = label
                                stack.append((nx, ny))
                label += 1
    return labeled_image