import httpx
import time

# Create a new job
print("Creating new translation job...")
r = httpx.post('http://localhost:8001/api/jobs', 
    files={'file': open('../examples/sample_english.srt', 'rb')}, 
    data={'target_lang': 'he'})
job = r.json()
job_id = job['job_id']
print(f"Job created: {job_id}")

# Poll for completion
print("Waiting for translation to complete...")
for i in range(120):  # Wait up to 4 minutes
    r = httpx.get(f'http://localhost:8001/api/jobs/{job_id}')
    status = r.json()
    print(f"  Status: {status['status']}, Progress: {status['progress']:.0f}%")
    if status['status'] == 'completed':
        break
    if status['status'] == 'failed':
        print(f"  ERROR: {status.get('error')}")
        break
    time.sleep(2)

# Get results and save to file
if status['status'] == 'completed':
    r = httpx.get(f'http://localhost:8001/api/jobs/{job_id}/result')
    data = r.json()
    
    with open("test_output.txt", "w", encoding="utf-8") as f:
        f.write("TRANSLATION RESULTS (First 10 subtitles):\n")
        f.write("=" * 80 + "\n\n")
        for s in data['segments'][:10]:
            f.write(f"#{s['index']}\n")
            f.write(f"  ORIGINAL:   {s['text']}\n")
            f.write(f"  TRANSLATED: {s['translated_text']}\n\n")
    
    print("Results saved to test_output.txt")
