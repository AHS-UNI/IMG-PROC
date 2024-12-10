const imageSelectionModal = document.getElementById('image-selection-modal');
const closeImageSelectionModalBtn = document.getElementById('close-image-selection-modal');
const modalImageList = document.getElementById('modal-image-list');
const confirmImageSelectionButton = document.getElementById('confirm-image-selection-button');


// coordinate logic
function cnvs_getCoordinates(event) {
    const imageElement = document.getElementById("workspace-image");
    const rect = imageElement.getBoundingClientRect();

    const scaleX = imageElement.naturalWidth / rect.width;
    const scaleY = imageElement.naturalHeight / rect.height;

    let x = event.clientX - rect.left;
    let y = event.clientY - rect.top;

    x = Math.max(0, Math.min(x, rect.width));
    y = Math.max(0, Math.min(y, rect.height));

    const imgX = Math.floor(x * scaleX);
    const imgY = Math.floor(y * scaleY);

    document.getElementById("workspace-coord-display").innerHTML = `Coordinates: (X: ${imgX}, Y: ${imgY})`;
}

function cnvs_clearCoordinates() {
    document.getElementById("workspace-coord-display").innerHTML = "Coordinates: (X: -, Y: -)";
}

function cnvs_getXCoord(event) {
    const imageElement = document.getElementById("histogram-image");
    const rect = imageElement.getBoundingClientRect();
    const scaleX = imageElement.naturalWidth / rect.width;

    let x = event.clientX - rect.left;

    x = Math.max(0, Math.min(x, rect.width));

    const imgX = Math.floor(x * scaleX);

    document.getElementById("histogram-x-coord-display").innerHTML = `Pixel Value: ${imgX}`;
}

function cnvs_clearXCoord() {
    document.getElementById("histogram-x-coord-display").innerHTML = "Pixel Value: -";
}

// global variables
let db;
let images = [];
let operationHistory = [];

// selectedImage: { id, imageBlob, histogramBlob, metadata }
let selectedImage = null;

// workspaceImage: { imageBlob, histogramBlob, metadata }
let workspaceImage = {
    imageBlob: null,
    histogramBlob: null,
    metadata: {}
};

let isWorkspaceModified = false;

function initializeWorkspaceImage() {
    fetch('https://dummyimage.com/500x500/&text=+')
        .then(response => response.blob())
        .then(blob => {
            workspaceImage.imageBlob = blob;
            return fetch('https://dummyimage.com/256x100/&text=+');
        })
        .then(response => response.blob())
        .then(blob => {
            workspaceImage.histogramBlob = blob;
            workspaceImage.metadata = {};
            renderWorkspace();
        })
        .catch(error => {
            console.error('Error initializing workspace image:', error);
        });
}

// persistence logic
function initDB() {
    const request = indexedDB.open('ImageDB', 1);

    request.onerror = (event) => {
        console.error('Database error:', event.target.errorCode);
    };

    request.onsuccess = (event) => {
        db = event.target.result;
        getAllImagesFromDB();
    };

    request.onupgradeneeded = (event) => {
        db = event.target.result;
        const objectStore = db.createObjectStore('images', { keyPath: 'id', autoIncrement: true });
        objectStore.createIndex('id', 'id', { unique: true });
    };
}

function addImageToDB(image) {
    const transaction = db.transaction(['images'], 'readwrite');
    const objectStore = transaction.objectStore('images');
    const request = objectStore.add(image);

    request.onsuccess = () => {
        image.id = request.result;
        images.push(image);
        renderImageList();
    };

    request.onerror = (event) => {
        console.error('Add image error:', event.target.error);
    };
}

function getAllImagesFromDB() {
    const transaction = db.transaction(['images'], 'readonly');
    const objectStore = transaction.objectStore('images');
    const request = objectStore.getAll();

    request.onsuccess = () => {
        images = request.result;
        renderImageList();
    };

    request.onerror = (event) => {
        console.error('Get all images error:', event.target.error);
    };
}

function deleteImageFromDB(id) {
    const transaction = db.transaction(['images'], 'readwrite');
    const objectStore = transaction.objectStore('images');
    const request = objectStore.delete(id);

    request.onsuccess = () => {
        const imageToDelete = images.find(image => image.id === id);
        if (imageToDelete) {
            if (imageToDelete.srcURL) URL.revokeObjectURL(imageToDelete.srcURL);
            if (imageToDelete.histogramURL) URL.revokeObjectURL(imageToDelete.histogramURL);
        }

        images = images.filter(image => image.id !== id);
        renderImageList();

        if (selectedImage && selectedImage.id === id) {
            clearWorkspace();
        }
    };

    request.onerror = (event) => {
        console.error('Delete image error:', event.target.error);
    };
}


// application logic
async function uploadImage() {
    const fileInput = document.getElementById('upload-image-file-input');
    const file = fileInput.files[0];
    if (!file) {
        alert('Please select an image to upload.');
        return;
    }

    try {
        const formData = new FormData();
        formData.append('file', file, file.name);

        const response = await fetch('http://127.0.0.1:8000/to_png', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Failed to convert image to PNG.');
        }

        const pngBlob = await response.blob();

        const histogramBlob = await fetchHistogram(pngBlob);
        const metadata = await fetchMetadata(pngBlob);

        if (!(pngBlob instanceof Blob)) {
            throw new Error('Invalid PNG Blob received.');
        }
        if (!(histogramBlob instanceof Blob)) {
            throw new Error('Invalid Histogram Blob received.');
        }

        const image = {
            imageBlob: pngBlob,
            histogramBlob: histogramBlob,
            metadata: metadata
        };

        addImageToDB(image);

        fileInput.value = '';
    } catch (error) {
        console.error('Upload image error:', error);
        alert('Error uploading image.');
    }
}

async function createImage() {
    const width = document.getElementById('create-image-width-input').value;
    const height = document.getElementById('create-image-height-input').value;
    const color = document.getElementById('create-image-color-input').value;

    if (!width || !height || !color) {
        alert('Please provide width, height, and color.');
        return;
    }

    try {
        const payload = {
            operation_type: 'create_image',
            width: parseInt(width),
            height: parseInt(height),
            color: color
        };

        const response = await fetch('http://127.0.0.1:8000/create_image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error('Failed to create image.');
        }

        const pngBlob = await response.blob();

        const histogramBlob = await fetchHistogram(pngBlob)
        const metadata = await fetchMetadata(pngBlob);

        if (!(pngBlob instanceof Blob)) {
            throw new Error('Invalid PNG Blob received.');
        }
        if (!(histogramBlob instanceof Blob)) {
            throw new Error('Invalid Histogram Blob received.');
        }

        const image = {
            imageBlob: pngBlob,
            histogramBlob: histogramBlob,
            metadata: metadata
        };

        addImageToDB(image);
    } catch (error) {
        console.error('Create image error:', error);
        alert('Error creating image.');
    }
}

async function fetchHistogram(imageBlob) {
    const formDataHistogram = new FormData();
    formDataHistogram.append('file', imageBlob, 'image.png'); // arbitrary file name

    const responseHistogram = await fetch('http://127.0.0.1:8000/histogram', {
        method: 'POST',
        body: formDataHistogram
    });

    if (!responseHistogram.ok) {
        throw new Error('Failed to fetch histogram.');
    }

    const histogramBlob = await responseHistogram.blob();
    return histogramBlob;
}

async function fetchMetadata(imageBlob) {
    const formDataMetadata = new FormData();
    formDataMetadata.append('file', imageBlob, 'image.png'); // arbitrary file name

    const responseMetadata = await fetch('http://127.0.0.1:8000/metadata', {
        method: 'POST',
        body: formDataMetadata
    });

    if (!responseMetadata.ok) {
        throw new Error('Failed to fetch metadata.');
    }

    const metadata = await responseMetadata.json();
    return metadata;
}

function renderImageList() {
    const imageList = document.getElementById('image-list');
    imageList.innerHTML = '';

    images.forEach(image => {
        if (!(image.imageBlob instanceof Blob) || !(image.histogramBlob instanceof Blob)) {
            console.warn(`Invalid blobs for image ID ${image.id}. Skipping rendering.`);
            return;
        }

        let srcURL, histogramURL;
        try {
            srcURL = URL.createObjectURL(image.imageBlob);
            histogramURL = URL.createObjectURL(image.histogramBlob);
        } catch (error) {
            console.error('Error creating Blob URLs:', error);
            return;
        }

        image.srcURL = srcURL;
        image.histogramURL = histogramURL;

        const img = document.createElement('img');
        img.src = srcURL;
        img.classList.add('thumbnail');
        img.dataset.id = image.id;

        if (selectedImage && selectedImage.id === image.id) {
            img.classList.add('selected');
        }

        img.addEventListener('click', () => selectImage(image.id));
        imageList.appendChild(img);
    });
}

function selectImage(id) {
    const image = images.find(img => img.id === id);
    if (!image) {
        alert('Selected image not found.');
        return;
    }

    selectedImage = {
        id: image.id,
        imageBlob: image.imageBlob,
        histogramBlob: image.histogramBlob,
        metadata: image.metadata
    };

    renderImageList();
}

function deleteSelectedImage() {
    if (!selectedImage) {
        alert('Please select an image to delete.');
        return;
    }

    deleteImageFromDB(selectedImage.id);
    selectedImage = null;
}

function loadImageIntoWorkspace() {
    if (!selectedImage) {
        alert('Please select an image to load into workspace.');
        return;
    }

    workspaceImage = selectedImage

    renderWorkspace();
}

function renderWorkspace() {
    const workspaceImgElement = document.getElementById('workspace-image');
    const histogramImgElement = document.getElementById('histogram-image');
    const metadataContent = document.getElementById('metadata-content');

    if (workspaceImgElement.src.startsWith('blob:')) {
        URL.revokeObjectURL(workspaceImgElement.src);
    }
    if (histogramImgElement.src.startsWith('blob:')) {
        URL.revokeObjectURL(histogramImgElement.src);
    }

    const newWorkspaceURL = URL.createObjectURL(workspaceImage.imageBlob);
    const newHistogramURL = URL.createObjectURL(workspaceImage.histogramBlob);

    workspaceImgElement.src = newWorkspaceURL;
    histogramImgElement.src = newHistogramURL;

    if (workspaceImage.metadata && Object.keys(workspaceImage.metadata).length > 0) {
        metadataContent.textContent = JSON.stringify(workspaceImage.metadata, null, 2);
    } else {
        metadataContent.textContent = '{}';
    }
}

function clearWorkspace() {
    const workspaceImgElement = document.getElementById('workspace-image');
    const histogramImgElement = document.getElementById('histogram-image');

    if (workspaceImgElement.src.startsWith('blob:')) {
        URL.revokeObjectURL(workspaceImgElement.src);
    }
    if (histogramImgElement.src.startsWith('blob:')) {
        URL.revokeObjectURL(histogramImgElement.src);
    }

    initializeWorkspaceImage();

    selectedImage = null;

    isWorkspaceModified = false;
}

function saveWorkspaceImage() {
    if (!workspaceImage.imageBlob) {
        alert('No image in workspace to save.');
        return;
    }

    const workspaceImgElement = document.getElementById('workspace-image');

    if (isWorkspaceModified) {
        const image = {
            imageBlob: workspaceImage.imageBlob,
            histogramBlob: workspaceImage.histogramBlob,
            metadata: workspaceImage.metadata
        };

        addImageToDB(image);
    }

    const link = document.createElement('a');
    link.href = workspaceImgElement.src;
    link.download = 'workspace-image.png';
    link.click();
}

// tab logic

function setActiveTab(clickedButton) {
    const tabButtons = document.querySelectorAll('#operation-tabs .operation-tab-link');

    const tabContents = document.querySelectorAll('.operation-tab-content');

    tabButtons.forEach(button => {
        button.disabled = false;
    });

    tabContents.forEach(content => {
        content.style.display = 'none';
    });

    clickedButton.disabled = true;

    const tabId = clickedButton.getAttribute('data-tab');
    const tabContent = document.getElementById(tabId);

    if (tabContent) {
        tabContent.style.display = 'grid';
    }
}

function initializeTabs() {
    const tabButtons = document.querySelectorAll('#operation-tabs .operation-tab-link');

    const tabContents = document.querySelectorAll('.operation-tab-content');

    tabContents.forEach(content => {
        if (content.id === 'default-operations-tab') {
            content.style.display = 'block';
        } else {
            content.style.display = 'none';
        }
    });

    tabButtons.forEach(button => {
        button.disabled = false;
    });
}

// extra settings logic
function initializeOperationExtraSettings() {
    const operationBlocks = document.querySelectorAll('.operation-tab-content .operation-block');

    operationBlocks.forEach(block => {
        const mainSettings = block.querySelector('.operation-main-settings');

        if (mainSettings) {
            const selectInputs = mainSettings.querySelectorAll('select[data-extra-setting]');

            selectInputs.forEach(select => {
                select.addEventListener('change', function() {
                    const settingName = this.getAttribute('data-extra-setting');
                    const selectedValue = this.value;

                    const extraSettings = block.querySelectorAll(`.extra-setting[data-extra-setting="${settingName}"]`);
                    extraSettings.forEach(setting => {
                        setting.style.display = 'none';
                    });

                    if (selectedValue) {
                        const targetSetting = block.querySelector(`.extra-setting[data-extra-setting="${settingName}"][data-extra-value="${selectedValue}"]`);
                        if (targetSetting) {
                            targetSetting.style.display = 'grid';
                        }
                    }
                });

                select.dispatchEvent(new Event('change'));
            });

            const checkboxInputs = mainSettings.querySelectorAll('input[type="checkbox"][data-extra-setting]');

            checkboxInputs.forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const settingName = this.getAttribute('data-extra-setting');
                    const isChecked = this.checked;

                    const extraSettings = block.querySelectorAll(`.extra-setting[data-extra-setting="${settingName}"]`);
                    extraSettings.forEach(setting => {
                        setting.style.display = 'none';
                    });

                    if (isChecked) {
                        const targetSetting = block.querySelector(`.extra-setting[data-extra-setting="${settingName}"][data-extra-value="true"]`);
                        if (targetSetting) {
                            targetSetting.style.display = 'grid';
                        }
                    }
                });

                checkbox.dispatchEvent(new Event('change'));
            });
        }
    });
}

// operation validation logic
function validateSelect(value, allowed, fieldName) {
    const errors = [];
    if (!value) {
        errors.push(`${fieldName} is required.`);
    } else if (!allowed.includes(value.toLowerCase())) {
        const allowedFormatted = allowed.map(val => `'${capitalize(val)}'`).join(' or ');
        errors.push(`${fieldName} must be either ${allowedFormatted}.`);
    }
    return errors;
}

function validateNumber(value, fieldName, min, max, isIntegerFlag = true, mustBeOdd = false) {
    const errors = [];
    const parsedValue = isIntegerFlag ? parseInteger(value) : parseFloatNumber(value);

    if (!value) {
        errors.push(`${fieldName} is required.`);
    } else if (parsedValue === null) {
        errors.push(`${fieldName} must be a ${isIntegerFlag ? 'integer' : 'number'}${isIntegerFlag ? '' : ' (decimal values allowed)'}${mustBeOdd ? ' and odd' : ''} between ${min} and ${max}.`);
    } else {
        if (!isInRange(parsedValue, min, max)) {
            errors.push(`${fieldName} must be between ${min} and ${max}.`);
        }
        if (mustBeOdd && !isOdd(parsedValue)) {
            errors.push(`${fieldName} must be an odd integer.`);
        }
    }

    return errors;
}

function validateCheckboxDependent(isChecked, fieldName, requiredFields) {
    const errors = [];
    if (isChecked) {
        requiredFields.forEach(field => {
            if (!field.value) {
                errors.push(`'${field.fieldName}' is required when '${fieldName}' is enabled.`);
            } else {
                const parsed = field.parseFunction(field.value);
                if (parsed === null) {
                    errors.push(`'${field.fieldName}' must be ${field.expectedType}.`);
                } else if (!isInRange(parsed, field.min, field.max)) {
                    errors.push(`'${field.fieldName}' must be between ${field.min} and ${field.max}.`);
                }
                if (field.mustBeOdd && !isOdd(parsed)) {
                    errors.push(`'${field.fieldName}' must be an odd integer.`);
                }
            }
        });
    }
    return errors;
}

function validategrayscale() {
    const mode = document.getElementById('grayscale-mode-input').value.trim().toLowerCase();
    return validateSelect(mode, ['lightness', 'luminosity'], 'Mode');
}

function validateHalftoning() {
    const colorMode = document.getElementById('halftoning-color-mode-input').value.trim().toLowerCase();
    const method = document.getElementById('halftoning-method-input').value.trim().toLowerCase(); // Fixed typo here
    const errors = [];

    errors.push(...validateSelect(colorMode, ['rgb', 'grayscale'], 'Color Mode'));

    errors.push(...validateSelect(method, ['thresholding', 'error_diffusion'], 'Method'));

    if (colorMode === 'rgb') {
        const redThreshold = document.getElementById('halftoning-r-threshold-input').value.trim();
        const greenThreshold = document.getElementById('halftoning-g-threshold-input').value.trim();
        const blueThreshold = document.getElementById('halftoning-b-threshold-input').value.trim();

        errors.push(...validateNumber(redThreshold, 'R-Channel Threshold', 0, 255));
        errors.push(...validateNumber(greenThreshold, 'G-Channel Threshold', 0, 255));
        errors.push(...validateNumber(blueThreshold, 'B-Channel Threshold', 0, 255));
    } else if (colorMode === 'grayscale') {
        const grayscaleThreshold = document.getElementById('halftoning-grayscale-threshold-input').value.trim();
        errors.push(...validateNumber(grayscaleThreshold, 'Threshold', 0, 255));
    }

    return errors;
}

function validateHistogramEqualization() {
    const mode = document.getElementById('histogram-equalization-color-mode-input').value.trim();
    return validateSelect(mode, ['rgb', 'grayscale'], 'Color Mode');
}

function validateHistogramSmoothing() {
    const colorMode = document.getElementById('histogram-smoothing-color-mode-input').value.trim();
    const kernelSizeInput = document.getElementById('histogram-smoothing-kernel-size-input').value.trim();
    const errors = [];

    errors.push(...validateSelect(colorMode, ['rgb', 'grayscale'], 'Color Mode'));

    errors.push(...validateNumber(kernelSizeInput, 'Kernel Size', 3, 255, true, true));

    return errors;
}

function validateBasicEdgeDetection() {
    const operator = document.getElementById('basic-edge-detection-operator-input').value.trim().toLowerCase();
    const thresholding = document.getElementById('basic-edge-detection-thresholding-input').checked;
    const contrastBased = document.getElementById('basic-edge-detection-contrast-input').checked;
    const errors = [];

    errors.push(...validateSelect(operator, ['roberts', 'sobel', 'prewitt', 'kirsch', 'robinson', 'laplacian_1', 'laplacian_2'], 'Operator'));

    const thresholdInput = document.getElementById('basic-edge-detection-threshold-input').value.trim();
    if (thresholding) {
        errors.push(...validateNumber(thresholdInput, 'Threshold', 0, 255));
    }

    const kernelSizeInput = document.getElementById('basic-edge-detection-smoothing-kernel-size-input').value.trim();
    if (contrastBased) {
        errors.push(...validateNumber(kernelSizeInput, 'Smoothing Kernel Size', 3, 999, true, true));
    }

    return errors;
}

function validateAdvancedEdgeDetection() {
    const operator = document.getElementById('advanced-edge-detection-operator-input').value.trim().toLowerCase();
    const thresholding = document.getElementById('advanced-edge-detection-thresholding-input').checked;
    const contrastBased = document.getElementById('advanced-edge-detection-contrast-input').checked;
    const errors = [];

    errors.push(...validateSelect(operator, ['homogeneity', 'difference', 'gaussian_1', 'gaussian_2', 'variance', 'range'], 'Operator'));

    const thresholdInput = document.getElementById('advanced-edge-detection-threshold-input').value.trim();
    if (thresholding) {
        errors.push(...validateNumber(thresholdInput, 'Threshold', 0, 255));
    }

    const kernelSizeInput = document.getElementById('advanced-edge-detection-smoothing-kernel-size-input').value.trim();
    if (contrastBased) {
        errors.push(...validateNumber(kernelSizeInput, 'Smoothing Kernel Size', 3, 999, true, true));
    }

    if (['homogeneity', 'difference'].includes(operator)) {
        if (contrastBased) {
            errors.push(`Contrast Based cannot be enabled for operator '${capitalize(operator)}'.`);
        }

        if (!thresholding) {
            errors.push('Thresholding is required for Homogeneity operator')
        }
    }

    if (['variance', 'range'].includes(operator)) {
        const kernelSizeInput = document.getElementById('advanced-edge-detection-kernel-size-input').value.trim();
        errors.push(...validateNumber(kernelSizeInput, 'Kernel Size', 3, 999, true, true));
    }

    return errors;
}

function validateFiltering() {
    const mode = document.getElementById('filtering-mode-input').value.trim().toLowerCase();
    const kernelSizeInput = document.getElementById('filtering-kernel-size-input').value.trim();
    const sigmaInput = document.getElementById('filtering-sigma-input').value.trim();
    const errors = [];

    errors.push(...validateSelect(mode, ['high', 'low', 'median'], 'Mode'));

    errors.push(...validateNumber(kernelSizeInput, 'Kernel Size', 3, 999, true, true));

    if (mode === 'median') {
        if (sigmaInput !== '') {
            errors.push("Median filter does not require a sigma value.");
        }
    } else {
        if (sigmaInput !== '') {
            const sigma = parseFloatNumber(sigmaInput);
            if (sigma === null) {
                errors.push("Sigma must be a valid number.");
            }
        }
    }

    return errors;
}

function validateSegmentation() {
    const mode = document.getElementById('histogram-based-segmentation-mode-input').value.trim().toLowerCase();
    const pixelValueInput = document.getElementById('histogram-based-segmentation-value-input').value.trim();
    const regionGrowing = document.getElementById('segmentation-segment-input').checked;
    const hiInput = document.getElementById('histogram-based-segmentation-hi-input').value.trim();
    const lowInput = document.getElementById('histogram-based-segmentation-low-input').value.trim();
    const errors = [];

    errors.push(...validateSelect(mode, ['manual', 'peak', 'valley', 'adaptive'], 'Mode'));

    errors.push(...validateNumber(pixelValueInput, 'Pixel Value', 0, 255));

    if (mode === 'manual') {
        if (!hiInput || !lowInput) {
            errors.push("'High Threshold' and 'Low Threshold' must be set for manual mode.");
        } else {
            errors.push(...validateNumber(hiInput, 'High Threshold', 0, 255));
            errors.push(...validateNumber(lowInput, 'Low Threshold', 0, 255));
        }
    }

    return errors;
}

function validateSingleImageOperations() {
    const operation = document.getElementById('single-image-operation-input').value.trim().toLowerCase();
    const errors = [];

    errors.push(...validateSelect(operation, ['rotate', 'flip', 'resize', 'invert'], 'Operation'));

    if (operation === 'rotate') {
        const angleInput = document.getElementById('single-image-rotate-angle-input').value.trim();
        const angle = parseFloatNumber(angleInput);
        if (!angleInput) {
            errors.push("Rotation Angle is required for 'Rotate' operation.");
        } else if (angle === null) {
            errors.push("Rotation Angle must be a valid number.");
        }
    }

    if (operation === 'flip') {
        const flipMode = document.getElementById('single-image-flip-mode-input').value.trim().toLowerCase();
        errors.push(...validateSelect(flipMode, ['horizontal', 'vertical'], 'Flip Mode'));
    }

    if (operation === 'resize') {
        const widthInput = document.getElementById('single-image-resize-width-input').value.trim();
        const heightInput = document.getElementById('single-image-resize-height-input').value.trim();
        errors.push(...validateNumber(widthInput, 'Width', 1, 10000)); 
        errors.push(...validateNumber(heightInput, 'Height', 1, 10000));
    }

    return errors;
}

function validateMultiImageOperations(operationData) {
    const errors = [];
    const { images, operation, src_region, dest_position } = operationData;
    
    if (!images || !Array.isArray(images) || images.length === 0) {
        errors.push("At least one image must be provided.");
    }
    
    if (!['add', 'subtract', 'cut_and_paste'].includes(operation)) {
        errors.push(`Invalid operation type: '${operation}'. Must be 'add', 'subtract', or 'cut_and_paste'.`);
    }
    
    if (operation === 'cut_and_paste') {
        if (images.length !== 2) {
            errors.push("Operation 'cut_and_paste' requires exactly two images (source and destination).");
        }
        if (!src_region || src_region.length !== 4) {
            errors.push("Operation 'cut_and_paste' requires 'src_region' as a tuple of four integers.");
        }
        if (!dest_position || dest_position.length !== 2) {
            errors.push("Operation 'cut_and_paste' requires 'dest_position' as a tuple of two integers.");
        }
    }
    
    if (['add', 'subtract'].includes(operation)) {
        // Ensure all images have the same dimensions as workspace image
        if (workspaceImage.metadata && workspaceImage.metadata.dimensions) {
            const { width, height } = workspaceImage.metadata.dimensions;
            images.forEach((imageBlob, index) => {
                const image = images.find(img => img.imageBlob === imageBlob);
                if (image && image.metadata && image.metadata.dimensions) {
                    if (image.metadata.dimensions.width !== width || image.metadata.dimensions.height !== height) {
                        errors.push(`Image ${index + 1} dimensions do not match the workspace image.`);
                    }
                } else {
                    errors.push(`Image ${index + 1} metadata is missing or incomplete.`);
                }
            });
        } else {
            errors.push("Workspace image dimensions are not available for validation.");
        }
    }
    
    return errors;
}

function attachValidationListeners() {
    const applyButtons = [
        { id: 'apply-grayscale-button', validate: validategrayscale, operationType: 'grayscale' },
        { id: 'apply-halftoning-button', validate: validateHalftoning, operationType: 'halftoning' },
        { id: 'apply-histogram-equalization-button', validate: validateHistogramEqualization, operationType: 'histogram_equalization' },
        { id: 'apply-histogram-smoothing-button', validate: validateHistogramSmoothing, operationType: 'histogram_smoothing' },
        { id: 'apply-basic-edge-detection-button', validate: validateBasicEdgeDetection, operationType: 'basic_edge_detection' },
        { id: 'apply-advanced-edge-detection-button', validate: validateAdvancedEdgeDetection, operationType: 'advanced_edge_detection' },
        { id: 'apply-filtering-button', validate: validateFiltering, operationType: 'filtering' },
        { id: 'apply-histogram-based-segmentation-button', validate: validateSegmentation, operationType: 'histogram_based_segmentation' },
        { id: 'apply-single-image-operation-button', validate: validateSingleImageOperations, operationType: 'single_image_operation' },
    ];

    applyButtons.forEach(button => {
        const applyBtn = document.getElementById(button.id);
        if (applyBtn) {
            const operationBlock = applyBtn.closest('.operation-block');
            const messageDiv = operationBlock.querySelector('.operation-message');

            applyBtn.addEventListener('click', async function(event) {
                event.preventDefault();

                const errors = button.validate();

                if (errors.length > 0) {
                    const formattedErrors = formatErrors(errors);
                    messageDiv.innerHTML = `<strong>Invalid operation:</strong><br>${formattedErrors}`;
                    messageDiv.style.color = 'red';
                } else {
                    messageDiv.innerHTML = "";
                    messageDiv.style.color = 'inherit';
                    const operationData = gatherOperationData(button.operationType);
                    await applyTransformation(operationData, button.operationType);
                }
            });
        }
    });
}

function gatherOperationData(operationType) {
    const data = { operation_type: operationType };

    switch (operationType) {
        case 'grayscale':
            data.mode = document.getElementById('grayscale-mode-input').value.trim().toLowerCase();
            break;
        case 'halftoning':
            data.method = document.getElementById('halftoning-method-input').value.trim().toLowerCase();
            data.mode = document.getElementById('halftoning-color-mode-input').value.trim().toLowerCase();
            if (data.mode === 'rgb') {
                r_channel_threshold = parseInteger(document.getElementById('halftoning-r-threshold-input').value.trim());
                g_channel_threshold = parseInteger(document.getElementById('halftoning-g-threshold-input').value.trim());
                b_channel_threshold = parseInteger(document.getElementById('halftoning-b-threshold-input').value.trim());
                data.threshold = [r_channel_threshold, g_channel_threshold, b_channel_threshold]
            } else if (data.mode === 'grayscale') {
                data.threshold = parseInteger(document.getElementById('halftoning-grayscale-threshold-input').value.trim());
            }
            break;
        case 'histogram_equalization':
            data.mode = document.getElementById('histogram-equalization-color-mode-input').value.trim().toLowerCase();
            break;
        case 'histogram_smoothing':
            data.mode = document.getElementById('histogram-smoothing-color-mode-input').value.trim().toLowerCase();
            data.kernel_size = parseInteger(document.getElementById('histogram-smoothing-kernel-size-input').value.trim());
            break;
        case 'basic_edge_detection':
            data.operator = document.getElementById('basic-edge-detection-operator-input').value.trim().toLowerCase();
            data.thresholding = document.getElementById('basic-edge-detection-thresholding-input').checked;
            data.contrast_based = document.getElementById('basic-edge-detection-contrast-input').checked;
            if (data.thresholding) {
                data.threshold = parseInteger(document.getElementById('basic-edge-detection-threshold-input').value.trim());
            }
            if (data.contrast_based) {
                data.smoothing_kernel_size = parseInteger(document.getElementById('basic-edge-detection-smoothing-kernel-size-input').value.trim());
            }
            break;
        case 'advanced_edge_detection':
            data.operator = document.getElementById('advanced-edge-detection-operator-input').value.trim().toLowerCase();
            data.thresholding = document.getElementById('advanced-edge-detection-thresholding-input').checked;
            data.contrast_based = document.getElementById('advanced-edge-detection-contrast-input').checked;
            if (data.thresholding) {
                data.threshold = parseInteger(document.getElementById('advanced-edge-detection-threshold-input').value.trim());
            }
            if (data.contrast_based) {
                data.smoothing_kernel_size = parseInteger(document.getElementById('advanced-edge-detection-smoothing-kernel-size-input').value.trim());
            }
            if (['variance', 'range'].includes(data.operator)) {
                data.kernel_size = parseInteger(document.getElementById('advanced-edge-detection-kernel-size-input').value.trim());
            }
            break;
        case 'filtering':
            data.mode = document.getElementById('filtering-mode-input').value.trim().toLowerCase();
            data.kernel_size = parseInteger(document.getElementById('filtering-kernel-size-input').value.trim());
            const sigmaInput = document.getElementById('filtering-sigma-input').value.trim();
            data.sigma = sigmaInput ? parseFloatNumber(sigmaInput) : null;
            break;
        case 'histogram_based_segmentation':
            data.mode = document.getElementById('histogram-based-segmentation-mode-input').value.trim().toLowerCase();
            data.value = parseInteger(document.getElementById('histogram-based-segmentation-value-input').value.trim());
            data.segment = document.getElementById('segmentation-segment-input').checked;
            if (data.mode === 'manual') {
                data.hi = parseInteger(document.getElementById('histogram-based-segmentation-hi-input').value.trim());
                data.low = parseInteger(document.getElementById('histogram-based-segmentation-low-input').value.trim());
            }
            break;
        case 'single_image_operation':
            data.operation = document.getElementById('single-image-operation-input').value.trim().toLowerCase();
            if (data.operation === 'rotate') {
                data.angle = parseFloatNumber(document.getElementById('single-image-rotate-angle-input').value.trim());
            }
            if (data.operation === 'flip') {
                data.mode = document.getElementById('single-image-flip-mode-input').value.trim().toLowerCase();
            }
            if (data.operation === 'resize') {
                width = parseInteger(document.getElementById('single-image-resize-width-input').value.trim());
                height = parseInteger(document.getElementById('single-image-resize-height-input').value.trim());
                data.output_size = [width, height]
            }
            break;
        default:
            console.warn(`Unknown operation type: ${operationType}`);
    }

    return data;
}

async function applyTransformation(operationData, operationType) {
    toggleApplyButtons(false);

    const formData = new FormData();
    formData.append('file', workspaceImage.imageBlob, 'workspace_image.png'); // Adjust filename and type as needed
    formData.append('operation_data', JSON.stringify(operationData));
    
    try {
        const transformedImageBlob = await fetchTransormedImage(workspaceImage.imageBlob, operationData);
        const transformedHistogramBlob = await fetchHistogram(transformedImageBlob);
        const transformedMetadata = await fetchMetadata(transformedImageBlob);

        const transformedImage = {
            imageBlob: transformedImageBlob,
            histogramBlob: transformedHistogramBlob,
            metadata: transformedMetadata
        }

        workspaceImage = transformedImage

        renderWorkspace()

        const operationDescription = formatOperationDescription(operationType, operationData);
        addToOperationHistory(operationDescription);
    } catch (error) {
        console.error('Apply transformation error:', error);
        alert('Error applying operation');
    } finally {
        toggleApplyButtons(true);
    }
}

async function fetchTransormedImage(imageBlob, operationData) {
    const formDataTransform = new FormData();
    formDataTransform.append('file', imageBlob, 'image.png'); // arbitrary file name
    formDataTransform.append('operation_data', JSON.stringify(operationData));

    const response = await fetch('http://127.0.0.1:8000/transform', {
        method: 'POST',
        headers: {
            'accept': 'application/json',
        },
        body: formDataTransform
    });

    if (!response.ok) {
        throw new Error(`Backend responded with status ${response.status}`);
    }

    const transformedImageBlob = await response.blob();
    return transformedImageBlob
}


function toggleApplyButtons(isEnabled) {
    const applyButtons = document.querySelectorAll('.apply-operation-button');
    applyButtons.forEach(button => {
        button.disabled = !isEnabled;
    });
}
function initializeOperationHistory() {
    operationHistory = [];
    renderOperationHistory();
}

function addToOperationHistory(operationDescription) {
    operationHistory.push(operationDescription);
    renderOperationHistory();
}

function renderOperationHistory() {
    const historyContent = document.getElementById('operation-history-content');
    historyContent.textContent = operationHistory.join('\n');
}

function formatOperationDescription(operationType, operationData) {
    let description = `Applied ${capitalize(operationType)} (`;
    const params = [];

    for (const [key, value] of Object.entries(operationData)) {
        if (key === 'operation_type') continue;
        // Format boolean values as true/false
        const formattedValue = typeof value === 'boolean' ? value : value;
        params.push(`${key.replace(/_/g, ' ')}: ${formattedValue}`);
    }

    description += params.join(', ') + ')';
    return description;
}

//  helper functions

function isInteger(value) {
    return Number.isInteger(value);
}

function isOdd(value) {
    return isInteger(value) && value % 2 !== 0;
}

function isInRange(value, min, max) {
    return value >= min && value <= max;
}

function parseInteger(value) {
    const parsed = parseInt(value, 10);
    return isNaN(parsed) ? null : parsed;
}

function parseFloatNumber(value) {
    const parsed = parseFloat(value);
    return isNaN(parsed) ? null : parsed;
}

function addError(errors, condition, message) {
    if (condition) {
        errors.push(message);
    }
}

function formatErrors(errors) {
    return errors.map(err => `<div>${err}</div>`).join('');
}


function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function openImageSelectionModal(operationType) {
    // Clear any previous selections
    modalImageList.innerHTML = '';
    
    // Determine selection constraints based on operation type
    let selectionLimit = Infinity;
    let filterDimensions = false;
    let requiredDimensions = null;
    let additionalConstraints = null;
    
    if (operationType === 'cut_and_paste') {
        selectionLimit = 2;
    } else if (operationType === 'add' || operationType === 'subtract') {
        filterDimensions = true;
        if (workspaceImage.metadata && workspaceImage.metadata.dimensions) {
            requiredDimensions = workspaceImage.metadata.dimensions; // Assuming dimensions are stored as { width: ..., height: ... }
        } else {
            alert('Workspace image dimensions not available for this operation.');
            return;
        }
    }
    
    // Filter images based on required dimensions if necessary
    const filteredImages = images.filter(image => {
        if (filterDimensions) {
            if (!image.metadata || !image.metadata.dimensions) return false;
            return image.metadata.dimensions.width === requiredDimensions.width &&
                   image.metadata.dimensions.height === requiredDimensions.height;
        }
        return true;
    });
    
    if (filterDimensions && filteredImages.length === 0) {
        alert('No images available with the same dimensions as the workspace image.');
        return;
    }
    
    // Populate the modal with filtered images
    filteredImages.forEach(image => {
        const imgElement = document.createElement('img');
        imgElement.src = URL.createObjectURL(image.imageBlob);
        imgElement.dataset.id = image.id;
        imgElement.addEventListener('click', () => toggleImageSelection(imgElement));
        modalImageList.appendChild(imgElement);
    });
    
    // Store the current operation type in the modal for later reference
    imageSelectionModal.dataset.operationType = operationType;
    
    // Show the modal
    imageSelectionModal.style.display = 'block';
}

/**
 * Toggles the selection state of an image in the modal.
 * @param {HTMLElement} imgElement - The image element clicked.
 */
function toggleImageSelection(imgElement) {
    const operationType = imageSelectionModal.dataset.operationType;
    const selectedImages = modalImageList.querySelectorAll('img.selected');
    
    if (operationType === 'cut_and_paste') {
        if (selectedImages.length >= 2 && !imgElement.classList.contains('selected')) {
            alert('You can only select up to 2 images for the Cut and Paste operation.');
            return;
        }
    }
    
    imgElement.classList.toggle('selected');
}

// Confirm Image Selection
confirmImageSelectionButton.addEventListener('click', () => {
    const operationType = imageSelectionModal.dataset.operationType;
    const selectedImages = modalImageList.querySelectorAll('img.selected');
    
    // Validation based on operation type
    if (operationType === 'cut_and_paste') {
        if (selectedImages.length !== 2) {
            alert('Cut and Paste operation requires exactly two images (source and destination).');
            return;
        }
    } else if (operationType === 'add' || operationType === 'subtract') {
        if (selectedImages.length === 0) {
            alert(`Please select at least one image for the ${operationType} operation.`);
            return;
        }
    }
    
    // Gather selected image blobs
    const selectedImageBlobs = Array.from(selectedImages).map(img => {
        const imageId = parseInt(img.dataset.id);
        const image = images.find(imgObj => imgObj.id === imageId);
        return image ? image.imageBlob : null;
    }).filter(blob => blob !== null);
    
    // Close the modal
    imageSelectionModal.style.display = 'none';
    clearModalSelections();
    
    // Prepare the operation data
    const operationData = {
        operation_type: 'multi_image_operation',
        operation: operationType
    };
    
    if (operationType === 'cut_and_paste') {
        operationData.images = selectedImageBlobs.slice(0, 2); // Assuming first is source, second is destination
        // Additional data like src_region and dest_position should be collected from the UI
        const srcRegionInput = document.getElementById('cut-and-paste-src-region-input');
        const destPositionInput = document.getElementById('cut-and-paste-dest-position-input');
        
        if (srcRegionInput && destPositionInput) {
            const srcRegionStr = srcRegionInput.value.trim();
            const destPositionStr = destPositionInput.value.trim();
            const srcRegion = srcRegionStr.split(',').map(Number);
            const destPosition = destPositionStr.split(',').map(Number);
            
            if (srcRegion.length === 4 && srcRegion.every(Number.isInteger)) {
                operationData.src_region = [srcRegion[0], srcRegion[1], srcRegion[2], srcRegion[3]];
            } else {
                alert("Source Region must be four comma-separated integers (x1,y1,x2,y2).");
                return;
            }
            
            if (destPosition.length === 2 && destPosition.every(Number.isInteger)) {
                operationData.dest_position = [destPosition[0], destPosition[1]];
            } else {
                alert("Destination Position must be two comma-separated integers (x,y).");
                return;
            }
        } else {
            alert('Source Region and Destination Position inputs are missing.');
            return;
        }
    } else {
        operationData.images = selectedImageBlobs;
    }
    
    // Validate the operation data before sending
    const validationErrors = validateMultiImageOperations(operationData);
    const operationMessageDiv = document.getElementById('multiple-image-operation-message');
    
    if (validationErrors.length > 0) {
        const formattedErrors = formatErrors(validationErrors);
        operationMessageDiv.innerHTML = `<strong>Invalid operation:</strong><br>${formattedErrors}`;
        operationMessageDiv.style.color = 'red';
    } else {
        operationMessageDiv.innerHTML = "";
        operationMessageDiv.style.color = 'inherit';
        // Send the operation to the backend
        applyMultipleImageTransformation(operationData, operationType);
    }
});

/**
 * Applies a multiple image transformation by sending data to the backend.
 * @param {Object} operationData - The operation data to send.
 * @param {string} operationType - The type of operation ('add', 'subtract', 'cut_and_paste').
 */
async function applyMultipleImageTransformation(operationData, operationType) {
    toggleApplyButtons(false);
    
    const formData = new FormData();
    operationData.images.forEach((imageBlob, index) => {
        formData.append('files', imageBlob, `image${index + 1}.png`); // Adjust filenames and types as needed
    });
    formData.append('operation_data', JSON.stringify({
        operation_type: 'multi_image_operation',
        operation: operationData.operation,
        src_region: operationData.src_region,
        dest_position: operationData.dest_position
    }));
    
    try {
        const response = await fetch('http://127.0.0.1:8000/transform_multi', {
            method: 'POST',
            headers: {
                'accept': 'application/json',
                // 'Content-Type' is automatically set to 'multipart/form-data' when using FormData
            },
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Backend responded with status ${response.status}`);
        }
        
        const transformedImageBlob = await response.blob();
        const transformedHistogramBlob = await fetchHistogram(transformedImageBlob);
        const transformedMetadata = await fetchMetadata(transformedImageBlob);
        
        workspaceImage = {
            imageBlob: transformedImageBlob,
            histogramBlob: transformedHistogramBlob,
            metadata: transformedMetadata
        };
        
        renderWorkspace();
        addToOperationHistory(`Applied Multiple Image Operation: ${capitalize(operationType)}`);
        
    } catch (error) {
        console.error('Apply multiple image transformation error:', error);
        alert('Error applying multiple image operation: ' + error.message);
    } finally {
        toggleApplyButtons(true);
    }
}

/**
 * Converts a base64 string to a Blob object.
 * @param {string} base64 - The base64 string.
 * @param {string} mime - The MIME type of the Blob.
 * @returns {Blob} - The resulting Blob.
 */
function base64ToBlob(base64, mime) {
    const byteCharacters = atob(base64);
    const byteArrays = [];
    
    for (let offset = 0; offset < byteCharacters.length; offset += 512) {
        const slice = byteCharacters.slice(offset, offset + 512);
        
        const byteNumbers = new Array(slice.length);
        for (let i = 0; i < slice.length; i++) {
            byteNumbers[i] = slice.charCodeAt(i);
        }
        
        const byteArray = new Uint8Array(byteNumbers);
        byteArrays.push(byteArray);
    }
    
    return new Blob(byteArrays, {type: mime});
}

// Modal Elements


function openImageSelectionModal(operationType) {
    // Clear any previous selections
    modalImageList.innerHTML = '';
    
    // Determine selection constraints based on operation type
    let selectionLimit = Infinity;
    let filterDimensions = false;
    let requiredDimensions = null;
    let additionalConstraints = null;
    
    if (operationType === 'cut_and_paste') {
        selectionLimit = 2;
    } else if (operationType === 'add' || operationType === 'subtract') {
        filterDimensions = true;
        if (workspaceImage.metadata && workspaceImage.metadata.dimensions) {
            requiredDimensions = workspaceImage.metadata.dimensions; // Assuming dimensions are stored as { width: ..., height: ... }
        } else {
            alert('Workspace image dimensions not available for this operation.');
            return;
        }
    }
    
    // Filter images based on required dimensions if necessary
    const filteredImages = images.filter(image => {
        if (filterDimensions) {
            if (!image.metadata || !image.metadata.dimensions) return false;
            return image.metadata.dimensions.width === requiredDimensions.width &&
                   image.metadata.dimensions.height === requiredDimensions.height;
        }
        return true;
    });
    
    if (filterDimensions && filteredImages.length === 0) {
        alert('No images available with the same dimensions as the workspace image.');
        return;
    }
    
    // Populate the modal with filtered images
    filteredImages.forEach(image => {
        const imgElement = document.createElement('img');
        imgElement.src = URL.createObjectURL(image.imageBlob);
        imgElement.dataset.id = image.id;
        imgElement.addEventListener('click', () => toggleImageSelection(imgElement));
        modalImageList.appendChild(imgElement);
    });
    
    // Store the current operation type in the modal for later reference
    imageSelectionModal.dataset.operationType = operationType;
    
    // Show the modal
    imageSelectionModal.style.display = 'block';
}

/**
 * Toggles the selection state of an image in the modal.
 * @param {HTMLElement} imgElement - The image element clicked.
 */
function toggleImageSelection(imgElement) {
    const operationType = imageSelectionModal.dataset.operationType;
    const selectedImages = modalImageList.querySelectorAll('img.selected');
    
    if (selectedImages.length >= (operationType === 'cut_and_paste' ? 2 : Infinity) && !imgElement.classList.contains('selected')) {
        alert(`You can select up to ${operationType === 'cut_and_paste' ? 2 : 'multiple'} images.`);
        return;
    }
    
    imgElement.classList.toggle('selected');
}


// Close the modal when the user clicks on the close button
closeImageSelectionModalBtn.onclick = function() {
    imageSelectionModal.style.display = 'none';
    clearModalSelections();
};

// Close the modal when the user clicks outside the modal content
window.onclick = function(event) {
    if (event.target === imageSelectionModal) {
        imageSelectionModal.style.display = 'none';
        clearModalSelections();
    }
};

/**
 * Clears all image selections in the modal.
 */
function clearModalSelections() {
    const selectedImages = modalImageList.querySelectorAll('img.selected');
    selectedImages.forEach(img => img.classList.remove('selected'));
}


confirmImageSelectionButton.addEventListener('click', () => {
    const operationType = imageSelectionModal.dataset.operationType;
    const selectedImages = modalImageList.querySelectorAll('img.selected');
    
    // Validation based on operation type
    if (operationType === 'cut_and_paste') {
        if (selectedImages.length !== 2) {
            alert('Cut and Paste operation requires exactly two images (source and destination).');
            return;
        }
    } else if (operationType === 'add' || operationType === 'subtract') {
        if (selectedImages.length === 0) {
            alert(`Please select at least one image for the ${operationType} operation.`);
            return;
        }
    }
    
    // Gather selected image blobs
    const selectedImageBlobs = Array.from(selectedImages).map(img => {
        const imageId = parseInt(img.dataset.id);
        const image = images.find(imgObj => imgObj.id === imageId);
        return image ? image.imageBlob : null;
    }).filter(blob => blob !== null);
    
    // Close the modal
    imageSelectionModal.style.display = 'none';
    clearModalSelections();
    
    // Prepare the operation data
    const operationData = {
        operation_type: 'multi_image_operation',
        operation: operationType
    };
    
    if (operationType === 'cut_and_paste') {
        operationData.images = selectedImageBlobs.slice(0, 2); // Assuming first is source, second is destination
        // Additional data like src_region and dest_position should be collected from the UI if required
        // For simplicity, assuming src_region and dest_position are collected from input fields elsewhere
        const srcRegionInput = document.getElementById('cut-and-paste-src-region-input'); // Ensure these inputs exist in HTML
        const destPositionInput = document.getElementById('cut-and-paste-dest-position-input');
        
        if (srcRegionInput && destPositionInput) {
            const srcRegion = srcRegionInput.value.trim().split(',').map(Number);
            const destPosition = destPositionInput.value.trim().split(',').map(Number);
            if (srcRegion.length === 4 && destPosition.length === 2) {
                operationData.src_region = [srcRegion[0], srcRegion[1], srcRegion[2], srcRegion[3]];
                operationData.dest_position = [destPosition[0], destPosition[1]];
            } else {
                alert('Invalid src_region or dest_position format. Please provide comma-separated values.');
                return;
            }
        } else {
            alert('src_region and dest_position inputs are missing.');
            return;
        }
    } else {
        operationData.images = selectedImageBlobs;
    }
    
    // Validate the operation data before sending
    const validationErrors = validateMultiImageOperations(operationData);
    const operationMessageDiv = document.getElementById('multiple-image-operation-message');
    
    if (validationErrors.length > 0) {
        const formattedErrors = formatErrors(validationErrors);
        operationMessageDiv.innerHTML = `<strong>Invalid operation:</strong><br>${formattedErrors}`;
        operationMessageDiv.style.color = 'red';
    } else {
        operationMessageDiv.innerHTML = "";
        operationMessageDiv.style.color = 'inherit';
        // Send the operation to the backend
        applyMultipleImageTransformation(operationData, operationType);
    }
});



// Event listeners and loading
function attachEventListeners() {
    document.getElementById('upload-image-button').addEventListener('click', uploadImage);
    document.getElementById('create-image-button').addEventListener('click', createImage);
    document.getElementById('delete-image-button').addEventListener('click', deleteSelectedImage);
    document.getElementById('load-image-button').addEventListener('click', loadImageIntoWorkspace);
    document.getElementById('clear-workspace-button').addEventListener('click', clearWorkspace);
    document.getElementById('save-workspace-button').addEventListener('click', saveWorkspaceImage);
    document.getElementById('browse-images-add').addEventListener('click', () => openImageSelectionModal('add'));
    document.getElementById('browse-images-subtract').addEventListener('click', () => openImageSelectionModal('subtract'));
    document.getElementById('browse-images-cut-and-paste').addEventListener('click', () => openImageSelectionModal('cut_and_paste'));


    const tabButtons = document.querySelectorAll('#operation-tabs .operation-tab-link');
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            setActiveTab(button);
        });
    });

    // Coordinate event listeners
    const workspaceCanvas = document.getElementById('workspace-image');
    workspaceCanvas.addEventListener('mousemove', cnvs_getCoordinates);
    workspaceCanvas.addEventListener('mouseout', cnvs_clearCoordinates);

    const histogramCanvas = document.getElementById('histogram-image');
    histogramCanvas.addEventListener('mousemove', cnvs_getXCoord);
    histogramCanvas.addEventListener('mouseout', cnvs_clearXCoord);
    
    // Modal close events are already handled above
}

window.onload = () => {
    initDB();
    initializeTabs();
    attachEventListeners();
    initializeWorkspaceImage();
    initializeOperationExtraSettings();
    initializeOperationHistory();
    attachValidationListeners();
};
