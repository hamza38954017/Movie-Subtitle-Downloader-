import os
import requests
from urllib.parse import quote
from flask import Flask, request, jsonify, render_template_string, Response

app = Flask(__name__)

# ==========================================
# CREDENTIALS & CONFIGURATION
# ==========================================
# We recommend setting these in Render's "Environment" tab later
API_KEY = os.environ.get("OPENSUBTITLES_API_KEY", "jnMaFtWskYAcAHv42xUovuPcanowNys5")
USERNAME = os.environ.get("OPENSUBTITLES_USERNAME", "crazydev") 
PASSWORD = os.environ.get("OPENSUBTITLES_PASSWORD", "hamza1") 
USER_AGENT = os.environ.get("OPENSUBTITLES_USER_AGENT", "MySubDownloader v1.0") 
BASE_URL = "https://api.opensubtitles.com/api/v1"

# ==========================================
# BACKEND API ROUTES
# ==========================================

@app.route('/api/fetch_subtitle', methods=['POST'])
def fetch_subtitle():
    movie = request.form.get('movie')
    if not movie:
        return jsonify({'error': 'Please enter a movie name.'}), 400

    # Step 1: Login
    login_res = requests.post(
        f"{BASE_URL}/login", 
        json={"username": USERNAME, "password": PASSWORD}, 
        headers={"Api-Key": API_KEY, "User-Agent": USER_AGENT, "Content-Type": "application/json"}
    )
    
    if login_res.status_code != 200:
        return jsonify({'error': 'Authentication failed. Check credentials.'}), 401
    
    token = login_res.json().get('token')

    # Step 2: Search for the movie
    search_res = requests.get(
        f"{BASE_URL}/subtitles", 
        params={"query": movie, "languages": "en"}, 
        headers={"Api-Key": API_KEY, "Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
    )
    
    if search_res.status_code != 200:
        return jsonify({'error': 'Failed to search OpenSubtitles database.'}), 500
        
    data = search_res.json().get('data', [])
    if not data:
        return jsonify({'error': f'No English subtitles found for "{movie}".'}), 404

    file_id = data[0]['attributes']['files'][0]['file_id']
    file_name = data[0]['attributes']['files'][0]['file_name']

    # Step 3: Get Download Link
    dl_res = requests.post(
        f"{BASE_URL}/download", 
        json={"file_id": file_id}, 
        headers={
            "Api-Key": API_KEY, 
            "Authorization": f"Bearer {token}", 
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    )
    
    if dl_res.status_code != 200:
        return jsonify({'error': 'Failed to retrieve the download link from the server.'}), 500

    download_link = dl_res.json().get('link')
    
    # Change extension to .txt
    txt_file_name = file_name.rsplit('.', 1)[0] + '.txt'

    # Return the URL to our own proxy route
    proxy_url = f"/api/serve?url={quote(download_link)}&name={quote(txt_file_name)}"
    return jsonify({'success': True, 'download_url': proxy_url})


@app.route('/api/serve', methods=['GET'])
def serve_file():
    """Fetches the file from OpenSubtitles and serves it as a clean .txt file."""
    url = request.args.get('url')
    name = request.args.get('name')
    
    if not url or not name:
        return "Missing parameters", 400

    # Fetch the file passing the User-Agent to prevent CDN blocking
    res = requests.get(url, headers={"User-Agent": USER_AGENT})
    
    if res.status_code != 200:
        return f"Failed to fetch file from OpenSubtitles. Status: {res.status_code}", 500

    # Force the browser to download it as a text file
    return Response(
        res.content,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment;filename="{name}"'}
    )

# ==========================================
# FRONTEND UI
# ==========================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Movie Subtitle Downloader</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
    </style>
</head>
<body class="gradient-bg min-h-screen flex flex-col justify-between text-gray-800">

    <main class="flex-grow flex items-center justify-center p-6">
        <div class="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-8">
            
            <div class="text-center mb-8">
                <div class="bg-indigo-100 text-indigo-600 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
                    <i class="fa-solid fa-closed-captioning"></i>
                </div>
                <h1 class="text-3xl font-bold text-gray-900">Movie Subtitle Downloader</h1>
                <p class="text-gray-500 mt-2">Find and download subtitles instantly as .txt files.</p>
            </div>

            <form id="downloadForm" class="space-y-5">
                <div>
                    <label for="movie" class="block text-sm font-medium text-gray-700 mb-1">Movie Name</label>
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <i class="fa-solid fa-film text-gray-400"></i>
                        </div>
                        <input type="text" id="movie" name="movie" required placeholder="e.g., Bheeshma" 
                            class="block w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm transition shadow-sm">
                    </div>
                </div>

                <button type="submit" id="submitBtn" class="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors">
                    <i class="fa-solid fa-download mr-2 mt-0.5"></i> Download Subtitle
                </button>
            </form>

            <div id="statusContainer" class="hidden mt-6">
                <div class="flex justify-between text-xs text-gray-500 mb-1">
                    <span id="statusText">Searching...</span>
                    <span id="progressText">0%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                    <div id="progressBar" class="bg-indigo-600 h-2 rounded-full transition-all duration-500 ease-out" style="width: 0%"></div>
                </div>
            </div>

            <div id="errorMessage" class="hidden mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm border border-red-200"></div>
            
            <div id="successMessage" class="hidden mt-4 p-3 bg-green-50 text-green-700 rounded-lg text-sm border border-green-200">
                <i class="fa-solid fa-check-circle mr-1"></i> Download starting! Your .txt file is ready.
            </div>

            <div class="mt-10 border-t border-gray-100 pt-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-4">Frequently Asked Questions</h3>
                <div class="space-y-4">
                    <details class="group bg-gray-50 rounded-lg">
                        <summary class="flex justify-between items-center font-medium cursor-pointer list-none p-4">
                            <span>What format are the subtitles?</span>
                            <span class="transition group-open:rotate-180">
                                <i class="fa-solid fa-chevron-down text-gray-400 text-sm"></i>
                            </span>
                        </summary>
                        <div class="text-gray-600 mt-2 px-4 pb-4 text-sm">
                            Subtitles are originally fetched as .srt formats but this tool automatically converts and saves them directly to your device as a plain text (.txt) file for easy reading.
                        </div>
                    </details>
                    <details class="group bg-gray-50 rounded-lg">
                        <summary class="flex justify-between items-center font-medium cursor-pointer list-none p-4">
                            <span>Are the subtitles free?</span>
                            <span class="transition group-open:rotate-180">
                                <i class="fa-solid fa-chevron-down text-gray-400 text-sm"></i>
                            </span>
                        </summary>
                        <div class="text-gray-600 mt-2 px-4 pb-4 text-sm">
                            Yes! We utilize the OpenSubtitles API which provides a massive, community-driven database of free subtitles.
                        </div>
                    </details>
                </div>
            </div>

        </div>
    </main>

    <footer class="bg-white/10 backdrop-blur-md py-4 text-center text-white text-sm">
        <p>Developer- Dr. Hamza</p>
    </footer>

    <script>
        document.getElementById('downloadForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const movieName = document.getElementById('movie').value;
            const submitBtn = document.getElementById('submitBtn');
            const statusContainer = document.getElementById('statusContainer');
            const progressBar = document.getElementById('progressBar');
            const statusText = document.getElementById('statusText');
            const progressText = document.getElementById('progressText');
            const errorMessage = document.getElementById('errorMessage');
            const successMessage = document.getElementById('successMessage');

            submitBtn.disabled = true;
            submitBtn.classList.add('opacity-70', 'cursor-not-allowed');
            errorMessage.classList.add('hidden');
            successMessage.classList.add('hidden');
            statusContainer.classList.remove('hidden');
            
            progressBar.style.width = '10%';
            progressText.innerText = '10%';
            statusText.innerText = 'Authenticating with API...';

            let progressInterval = setInterval(() => {
                let currentWidth = parseInt(progressBar.style.width);
                if (currentWidth < 85) {
                    progressBar.style.width = (currentWidth + 5) + '%';
                    progressText.innerText = (currentWidth + 5) + '%';
                    if(currentWidth > 30) statusText.innerText = 'Searching database...';
                    if(currentWidth > 60) statusText.innerText = 'Generating .txt file...';
                }
            }, 600);

            const formData = new FormData();
            formData.append('movie', movieName);

            fetch('/api/fetch_subtitle', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                clearInterval(progressInterval);
                
                if (data.error) {
                    throw new Error(data.error);
                }

                progressBar.style.width = '100%';
                progressText.innerText = '100%';
                statusText.innerText = 'Complete!';
                successMessage.classList.remove('hidden');

                setTimeout(() => {
                    window.location.href = data.download_url;
                    resetUI();
                }, 1000);

            })
            .catch(error => {
                clearInterval(progressInterval);
                statusContainer.classList.add('hidden');
                errorMessage.innerText = error.message || 'Network error occurred.';
                errorMessage.classList.remove('hidden');
                resetUI();
            });

            function resetUI() {
                submitBtn.disabled = false;
                submitBtn.classList.remove('opacity-70', 'cursor-not-allowed');
                setTimeout(() => {
                    progressBar.style.width = '0%';
                }, 2000);
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # This runs the app locally if you test it on your computer
    app.run(debug=True)
