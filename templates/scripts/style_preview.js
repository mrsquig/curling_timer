function get_style_img(inputData, img_node, header_node, header_txt) {
    fetch('/style_img', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(inputData),
    })
    .then(response => response.blob())  // Get the image blob response
    .then(imageBlob => {
        // Create a URL for the image blob
        const imageUrl = URL.createObjectURL(imageBlob);

        // Show the generated image
        img_node.src = imageUrl;
        img_node.style.display = 'block';

        // Set the header to have text now that there is an image
        header_node.innerText = header_txt;
    })
    .catch(error => console.error('Error:', error));
}

document.getElementById('preview_style_btn').addEventListener('click', function() {
    event.preventDefault();

    // Collect form data
    inputData = get_form_data();
    inputData["image_settings"]["image_type"] = "normal";

    // Send input data as JSON to the server to get the image for
    // the normal style
    get_style_img(inputData,
                  document.getElementById('generated_image'),
                  document.getElementById("normal_header"),
                  "Normal style");

    // Get the image for the first warning
    inputData["image_settings"]["image_type"] = "warning_1";
    get_style_img(inputData,
                  document.getElementById('generated_image_warning_1'),
                  document.getElementById("warning_1_header"),
                  "Warning #1");

    // Get the image for the second warning
    inputData["image_settings"]["image_type"] = "warning_2";
    get_style_img(inputData,
                  document.getElementById('generated_image_warning_2'),
                  document.getElementById("warning_2_header"),
                  "Warning #2");
}
);