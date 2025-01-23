document.getElementById('upload-form').addEventListener('submit', async function (e) {
    e.preventDefault();

    const fileInput = document.getElementById('file');
    const languageSelect = document.getElementById('language');
    const responseMessage = document.getElementById('response-message');
    const originalTextArea = document.getElementById('original-text');
    const translatedTextArea = document.getElementById('translated-text');
    const audioSection = document.getElementById('audio-section');
    const audioPlayer = document.getElementById('translated-audio');

    // Reset previous results
    originalTextArea.value = '';
    translatedTextArea.value = '';
    responseMessage.textContent = '';
    audioSection.style.display = 'none';
    audioPlayer.src = '';

    if (!fileInput.files[0]) {
        responseMessage.textContent = "Please upload a file.";
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('language', languageSelect.value);

    responseMessage.textContent = "Processing... Please wait. It may take a few minutes based on the file size";

    try {
        const response = await fetch('/translate', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.error || "Unexpected server error.");
        }

        const result = await response.json();
        originalTextArea.value = result.original_text;
        translatedTextArea.value = result.translated_text;

        // Handle PDF download
        const blob = await fetch(`/download/${result.filename}`).then(r => r.blob());
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'translated.pdf';
        document.body.appendChild(a);
        a.click();
        a.remove();

        // Handle Audio
        if (result.audio_filename) {
            const audioBlob = await fetch(`/audio/${result.audio_filename}`).then(r => r.blob());
            audioPlayer.src = URL.createObjectURL(audioBlob);
            audioSection.style.display = 'block';
        }

        responseMessage.textContent = "Translation completed. Downloading...";
    } catch (error) {
        responseMessage.textContent = `Error: ${error.message}`;
    }
});