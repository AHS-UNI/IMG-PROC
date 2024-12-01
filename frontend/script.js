// frontend/script.js
document.addEventListener("DOMContentLoaded", () => {
  const imageInput = document.getElementById("imageInput");
  const imageContainer = document.getElementById("imageContainer");
  const uploadedImage = document.getElementById("uploadedImage");
  const metadataDiv = document.getElementById("metadata");
  const histogramR = document.getElementById("histogramR");
  const histogramG = document.getElementById("histogramG");
  const histogramB = document.getElementById("histogramB");

  imageInput.addEventListener("change", () => {
    const file = imageInput.files[0];
    if (file) {
      // Display the uploaded image
      const reader = new FileReader();
      reader.onload = (e) => {
        uploadedImage.src = e.target.result;
      };
      reader.readAsDataURL(file);

      // Prepare form data
      const formData = new FormData();
      formData.append("file", file);

      // Send image to backend
      fetch("/upload/", {
        method: "POST",
        body: formData,
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.error) {
            alert(`Error: ${data.error}`);
            return;
          }

          // Display image from cache (to handle server-side processing)
          uploadedImage.src = data.image_url;
          imageContainer.style.display = "block";

          // Display metadata
          metadataDiv.textContent = JSON.stringify(
            data.metadata, null, 2
          );

          // Display histograms
          histogramR.src = `../cache/${data.session_id}/histogram_R.png`;
          histogramG.src = `../cache/${data.session_id}/histogram_G.png`;
          histogramB.src = `../cache/${data.session_id}/histogram_B.png`;
        })
        .catch((error) => {
          console.error("Error:", error);
          alert("An error occurred while uploading the image.");
        });
    }
  });
});
