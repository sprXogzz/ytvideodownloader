const form = document.getElementById('form');
const urlInput = document.getElementById('url');
const progressEl = document.getElementById('progress');
const percentEl = document.getElementById('percent');
const titleEl = document.getElementById('title');
const sizeEl = document.getElementById('size');
const thumbEl = document.getElementById('thumbnail');
const msgEl = document.getElementById('message');
const downloadBtn = document.getElementById('download-btn');

let pollInterval = null;

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    
    try {
        await fetch('/download', { method: 'POST', body: formData });
        msgEl.innerText = "İndirme başlatıldı...";
        startPolling();
    } catch (err) {
        msgEl.innerText = "Başlatılamadı: " + err;
    }
});

function startPolling(){
    if(pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
        try {
            const r = await fetch('/progress');
            const data = await r.json();
            
            // UI güncellemesi
            titleEl.innerText = data.title ? data.title : "Başlık: -";
            sizeEl.innerText = "Boyut: " + (data.size || "-");
            percentEl.innerText = "%" + (Number(data.progress || 0).toFixed(1));
            progressEl.style.width = (Number(data.progress||0)) + "%";

            if(data.thumbnail){
                thumbEl.style.backgroundImage = `url(${data.thumbnail})`;
            }

            // Backend mesajını göster (örn. playlist uyarısı)
            msgEl.innerText = data.message || "";

            if(data.status === 'finished'){
                if(!msgEl.innerText) msgEl.innerText = "✅ Hazır!";
                downloadBtn.style.display = "inline-block";
                downloadBtn.onclick = async () => {
                    const res = await fetch('/getfile');
                    if(res.ok){
                        const blob = await res.blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        
                        let fname = data.title || 'video';
                        fname = fname.replace(/[\\\/:*?"<>|]/g, '').trim();
                        a.href = url;
                        a.download = fname + (data.filepath && data.filepath.endsWith('.mp4') ? '.mp4' : '.mp3');
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                    } else {
                        alert('Dosya alınamadı');
                    }
                };
                clearInterval(pollInterval);
            } else if(data.status === 'error'){
                msgEl.innerText = "❌ Hata: " + (data.error || 'Unknown');
                clearInterval(pollInterval);
            }
        } catch(err){
            msgEl.innerText = "Polling error: " + err;
        }
    }, 800);
}
