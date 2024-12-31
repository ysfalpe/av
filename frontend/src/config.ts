export const config = {
    API_URL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
    MAX_FILE_SIZE: 104857600, // 100MB
    SUPPORTED_FORMATS: ['video/mp4', 'video/x-msvideo', 'video/quicktime', 'video/webm'],
    MAX_VIDEO_DURATION: 600, // 10 dakika
    DEFAULT_DB_TARGET: -20,
    SUBTITLE_COLORS: ['white', 'yellow', 'green', 'cyan', 'red'],
    EXPORT_FORMATS: ['srt', 'vtt']
}; 