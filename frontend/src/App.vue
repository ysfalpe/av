<template>
  <div class="app">
    <!-- Header -->
    <header>
      <h1>Video Alt Yazı Oluşturucu</h1>
      <div class="new-year-badge">🎄 Yeni Yıl 2024 🎄</div>
    </header>

    <!-- Ana içerik -->
    <main>
      <!-- Bilgi kutusu -->
      <div class="info-box">
        <h3>Desteklenen Formatlar ve Limitler</h3>
        <ul>
          <li>Formatlar: MP4, AVI, MOV, WebM</li>
          <li>Maksimum boyut: 100MB</li>
          <li>Maksimum süre: 10 dakika</li>
        </ul>
      </div>

      <!-- Dosya yükleme alanı -->
      <div 
        class="upload-container"
        @dragover.prevent="handleDragOver"
        @dragleave.prevent="handleDragLeave"
        @drop.prevent="handleDrop"
        :class="{ 'drag-over': isDragging }"
      >
        <div v-if="!selectedFile && !isUploading">
          <i class="fas fa-cloud-upload-alt"></i>
          <p>Dosyayı sürükleyip bırakın veya seçin</p>
          <input 
            type="file" 
            ref="fileInput" 
            @change="handleFileSelect" 
            accept=".mp4,.avi,.mov,.webm"
            class="file-input"
          >
          <button @click="$refs.fileInput.click()" class="select-button">
            Dosya Seç
          </button>
        </div>

        <div v-else-if="selectedFile && !isUploading" class="file-preview">
          <div class="file-info">
            <p>{{ selectedFile.name }}</p>
            <p>{{ formatFileSize(selectedFile.size) }}</p>
          </div>
          
          <!-- Video önizleme -->
          <video 
            v-if="videoPreviewUrl" 
            ref="videoPreview" 
            controls 
            class="video-preview"
          >
            <source :src="videoPreviewUrl" :type="selectedFile.type">
          </video>

          <!-- Ses normalizasyonu seçenekleri -->
          <div class="audio-options">
            <label>
              <input 
                type="checkbox" 
                v-model="normalizeAudio"
              > Ses seviyesini normalize et
            </label>
            <div v-if="normalizeAudio" class="db-slider">
              <label>Hedef dB: {{ targetDb }}</label>
              <input 
                type="range" 
                v-model="targetDb" 
                min="-30" 
                max="-10" 
                step="1"
              >
            </div>
          </div>

          <div class="action-buttons">
            <button @click="uploadFile" class="upload-button">Yükle</button>
            <button @click="cancelSelection" class="cancel-button">İptal</button>
          </div>
        </div>

        <!-- Yükleme durumu -->
        <div v-else class="upload-status">
          <div class="progress-container">
            <div 
              class="progress-bar" 
              :style="{ width: `${uploadProgress}%` }"
            ></div>
          </div>
          <p>{{ uploadStatus }}</p>
          <p v-if="estimatedTime">Tahmini süre: {{ estimatedTime }}</p>
          <button 
            v-if="canCancel" 
            @click="cancelUpload" 
            class="cancel-button"
          >
            İptal Et
          </button>
        </div>
      </div>

      <!-- Alt yazı düzenleme alanı -->
      <div v-if="subtitles.length > 0" class="subtitle-editor">
        <h3>Alt Yazı Düzenleme</h3>
        
        <!-- Zaman ayarı -->
        <div class="timing-adjustment">
          <label>Zaman Düzeltme (saniye):</label>
          <input 
            type="number" 
            v-model="timeOffset" 
            step="0.1"
          >
          <button @click="adjustTiming">Uygula</button>
        </div>

        <!-- Renk seçimi -->
        <div class="color-selection">
          <label>Alt Yazı Rengi:</label>
          <select v-model="subtitleColor">
            <option value="white">Beyaz</option>
            <option value="yellow">Sarı</option>
            <option value="green">Yeşil</option>
            <option value="cyan">Mavi</option>
            <option value="red">Kırmızı</option>
          </select>
        </div>

        <!-- Dışa aktarma -->
        <div class="export-options">
          <label>Format:</label>
          <select v-model="exportFormat">
            <option value="srt">SRT</option>
            <option value="vtt">VTT</option>
          </select>
          <button @click="exportSubtitles">Dışa Aktar</button>
        </div>

        <!-- Alt yazı listesi -->
        <div class="subtitles-list">
          <div 
            v-for="(sub, index) in subtitles" 
            :key="index"
            class="subtitle-item"
          >
            <div class="subtitle-time">
              {{ formatTime(sub.start) }} - {{ formatTime(sub.end) }}
            </div>
            <div 
              class="subtitle-text"
              :style="{ color: subtitleColor }"
            >
              {{ sub.text }}
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Kar efekti -->
    <div class="snowfall"></div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'

export default {
  name: 'App',
  setup() {
    // Durum değişkenleri
    const selectedFile = ref(null)
    const videoPreviewUrl = ref(null)
    const isUploading = ref(false)
    const uploadProgress = ref(0)
    const uploadStatus = ref('')
    const estimatedTime = ref('')
    const canCancel = ref(true)
    const isDragging = ref(false)
    const subtitles = ref([])
    const timeOffset = ref(0)
    const subtitleColor = ref('white')
    const exportFormat = ref('srt')
    const normalizeAudio = ref(false)
    const targetDb = ref(-20)
    const currentTaskId = ref(null)

    // Dosya seçimi
    const handleFileSelect = (event) => {
      const file = event.target.files[0]
      if (validateFile(file)) {
        selectedFile.value = file
        createVideoPreview(file)
      }
    }

    // Dosya doğrulama
    const validateFile = (file) => {
      const maxSize = 100 * 1024 * 1024 // 100MB
      const allowedTypes = ['video/mp4', 'video/x-msvideo', 'video/quicktime', 'video/webm']

      if (!allowedTypes.includes(file.type)) {
        alert('Desteklenmeyen dosya formatı')
        return false
      }

      if (file.size > maxSize) {
        alert('Dosya boyutu çok büyük (Maksimum 100MB)')
        return false
      }

      return true
    }

    // Video önizleme
    const createVideoPreview = (file) => {
      videoPreviewUrl.value = URL.createObjectURL(file)
    }

    // Dosya boyutu formatı
    const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 Bytes'
      const k = 1024
      const sizes = ['Bytes', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }

    // Zaman formatı
    const formatTime = (seconds) => {
      const h = Math.floor(seconds / 3600)
      const m = Math.floor((seconds % 3600) / 60)
      const s = Math.floor(seconds % 60)
      const ms = Math.floor((seconds % 1) * 1000)
      return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`
    }

    // Dosya yükleme
    const uploadFile = async () => {
      if (!selectedFile.value) return

      isUploading.value = true
      uploadProgress.value = 0
      uploadStatus.value = 'Yükleniyor...'

      const formData = new FormData()
      formData.append('file', selectedFile.value)
      formData.append('normalize_sound', normalizeAudio.value)
      formData.append('target_db', targetDb.value)

      try {
        const response = await fetch('http://localhost:8000/upload-video/', {
          method: 'POST',
          body: formData
        })

        if (!response.ok) {
          throw new Error('Yükleme başarısız')
        }

        const data = await response.json()
        currentTaskId.value = data.task_id
        
        // Görev durumunu kontrol et
        checkTaskStatus()
      } catch (error) {
        console.error('Yükleme hatası:', error)
        uploadStatus.value = 'Yükleme başarısız: ' + error.message
        isUploading.value = false
      }
    }

    // Görev durumu kontrolü
    const checkTaskStatus = async () => {
      if (!currentTaskId.value) return

      try {
        const response = await fetch(`http://localhost:8000/task/${currentTaskId.value}`)
        const data = await response.json()

        if (data.state === 'SUCCESS') {
          uploadStatus.value = 'İşlem tamamlandı'
          uploadProgress.value = 100
          isUploading.value = false
          subtitles.value = data.result
        } else if (data.state === 'FAILURE') {
          throw new Error(data.error)
        } else {
          uploadProgress.value = data.progress || 0
          setTimeout(checkTaskStatus, 1000)
        }
      } catch (error) {
        console.error('Durum kontrolü hatası:', error)
        uploadStatus.value = 'İşlem başarısız: ' + error.message
        isUploading.value = false
      }
    }

    // Alt yazı zamanlaması ayarlama
    const adjustTiming = async () => {
      if (!currentTaskId.value) return

      try {
        const response = await fetch(`http://localhost:8000/adjust-timing/${currentTaskId.value}?offset=${timeOffset.value}`, {
          method: 'POST'
        })

        if (!response.ok) {
          throw new Error('Zamanlama ayarı başarısız')
        }

        const data = await response.json()
        subtitles.value = data.subtitles
      } catch (error) {
        console.error('Zamanlama ayarı hatası:', error)
        alert('Zamanlama ayarı başarısız: ' + error.message)
      }
    }

    // Alt yazıları dışa aktarma
    const exportSubtitles = async () => {
      if (!currentTaskId.value) return

      try {
        const response = await fetch(
          `http://localhost:8000/export-subtitles/${currentTaskId.value}?format=${exportFormat.value}&color=${subtitleColor.value}`
        )

        if (!response.ok) {
          throw new Error('Dışa aktarma başarısız')
        }

        // Dosyayı indir
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `subtitles_${currentTaskId.value}.${exportFormat.value}`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      } catch (error) {
        console.error('Dışa aktarma hatası:', error)
        alert('Dışa aktarma başarısız: ' + error.message)
      }
    }

    // Sürükle-bırak işlemleri
    const handleDragOver = (event) => {
      isDragging.value = true
    }

    const handleDragLeave = (event) => {
      isDragging.value = false
    }

    const handleDrop = (event) => {
      isDragging.value = false
      const file = event.dataTransfer.files[0]
      if (validateFile(file)) {
        selectedFile.value = file
        createVideoPreview(file)
      }
    }

    // Seçimi iptal et
    const cancelSelection = () => {
      selectedFile.value = null
      videoPreviewUrl.value = null
      uploadProgress.value = 0
      uploadStatus.value = ''
    }

    // Yüklemeyi iptal et
    const cancelUpload = () => {
      // TODO: Backend'de iptal mekanizması eklendiğinde implement edilecek
      isUploading.value = false
      uploadProgress.value = 0
      uploadStatus.value = 'İptal edildi'
    }

    return {
      selectedFile,
      videoPreviewUrl,
      isUploading,
      uploadProgress,
      uploadStatus,
      estimatedTime,
      canCancel,
      isDragging,
      subtitles,
      timeOffset,
      subtitleColor,
      exportFormat,
      normalizeAudio,
      targetDb,
      handleFileSelect,
      formatFileSize,
      formatTime,
      uploadFile,
      adjustTiming,
      exportSubtitles,
      handleDragOver,
      handleDragLeave,
      handleDrop,
      cancelSelection,
      cancelUpload
    }
  }
}
</script>

<style>
.app {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  font-family: Arial, sans-serif;
  position: relative;
  min-height: 100vh;
}

header {
  text-align: center;
  margin-bottom: 40px;
  position: relative;
}

.new-year-badge {
  position: absolute;
  top: -10px;
  right: -10px;
  background: linear-gradient(45deg, #ff4d4d, #ff9999);
  padding: 5px 15px;
  border-radius: 20px;
  color: white;
  font-weight: bold;
  animation: pulse 2s infinite;
}

.info-box {
  background: #f8f9fa;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.upload-container {
  border: 3px dashed #ccc;
  border-radius: 10px;
  padding: 40px;
  text-align: center;
  transition: all 0.3s ease;
  background: white;
  margin-bottom: 30px;
}

.drag-over {
  border-color: #4CAF50;
  background: #f1f8e9;
}

.file-input {
  display: none;
}

.select-button {
  background: #2196F3;
  color: white;
  padding: 10px 20px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: background 0.3s ease;
}

.select-button:hover {
  background: #1976D2;
}

.file-preview {
  max-width: 600px;
  margin: 0 auto;
}

.video-preview {
  max-width: 100%;
  margin: 20px 0;
  border-radius: 5px;
}

.progress-container {
  width: 100%;
  height: 20px;
  background: #f0f0f0;
  border-radius: 10px;
  overflow: hidden;
  margin: 20px 0;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #4CAF50, #8BC34A);
  transition: width 0.3s ease;
}

.action-buttons {
  margin-top: 20px;
}

.upload-button, .cancel-button {
  padding: 10px 20px;
  margin: 0 10px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.upload-button {
  background: #4CAF50;
  color: white;
}

.cancel-button {
  background: #f44336;
  color: white;
}

.subtitle-editor {
  background: white;
  border-radius: 10px;
  padding: 20px;
  margin-top: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.timing-adjustment, .color-selection, .export-options {
  margin: 20px 0;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 5px;
}

.subtitles-list {
  max-height: 400px;
  overflow-y: auto;
  padding: 10px;
}

.subtitle-item {
  padding: 10px;
  margin: 5px 0;
  background: #f8f9fa;
  border-radius: 5px;
}

.subtitle-time {
  font-size: 0.9em;
  color: #666;
}

.audio-options {
  margin: 20px 0;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 5px;
}

.db-slider {
  margin-top: 10px;
}

/* Kar efekti */
.snowfall {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: -1;
  background: linear-gradient(transparent, rgba(255,255,255,0.3));
  animation: snow 10s linear infinite;
}

@keyframes snow {
  0% {
    background-position: 0 0;
  }
  100% {
    background-position: 500px 1000px;
  }
}

@keyframes pulse {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
  100% {
    transform: scale(1);
  }
}
</style> 