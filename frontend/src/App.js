import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Upload, Download, Sun, Moon, Trash2, X } from 'lucide-react';
import './App.css';

function App() {
  const [darkMode, setDarkMode] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [albums, setAlbums] = useState({});
  const [isClearing, setIsClearing] = useState(false);
  const [modalImage, setModalImage] = useState(null);

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
      setDarkMode(true);
      document.documentElement.setAttribute('data-theme', 'dark');
    }
    fetchAlbums();
  }, []);

  const toggleTheme = () => {
    const newDarkMode = !darkMode;
    setDarkMode(newDarkMode);
    if (newDarkMode) {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('theme', 'light');
    }
  };

  const openModal = (imageUrl) => {
    setModalImage(imageUrl);
    document.body.classList.add('modal-open');
  };

  const closeModal = () => {
    setModalImage(null);
    document.body.classList.remove('modal-open');
  };

  const fetchAlbums = async () => {
    try {
      const response = await axios.get('/albums');
      setAlbums(response.data);
    } catch (err) {
      console.error('Ошибка загрузки альбомов:', err);
    }
  };

  const handleFileChange = (event) => {
    setSelectedFiles(Array.from(event.target.files));
    setError(null);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      setError('Пожалуйста, выберите хотя бы один файл');
      return;
    }

    const formData = new FormData();
    selectedFiles.forEach(file => formData.append('files', file));

    setIsUploading(true);
    setUploadProgress(0);

    try {
      await axios.post('/upload', formData, {
        onUploadProgress: (progressEvent) => {
          const progress = Math.round(
            (progressEvent.loaded / progressEvent.total) * 100
          );
          setUploadProgress(progress);
        },
      });
      await fetchAlbums();
      setSelectedFiles([]);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.error || 'Ошибка загрузки файлов');
      console.error('Ошибка загрузки:', err);
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDownload = async (albumName) => {
    try {
      const response = await axios.get(`/download/${albumName}`, {
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${albumName}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      setError('Ошибка загрузки альбома');
      console.error('Ошибка скачивания:', err);
    }
  };

  const handleClearAll = async () => {
    if (window.confirm('Вы уверены, что хотите удалить все фото и альбомы? Это действие нельзя отменить.')) {
      setIsClearing(true);
      try {
        await axios.delete('/clear');
        setAlbums({});
        setError(null);
      } catch (err) {
        setError(err.response?.data?.error || 'Ошибка при очистке');
        console.error('Ошибка очистки:', err);
      } finally {
        setIsClearing(false);
      }
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Автоматический фотоальбом</h1>
        <p>Загрузите фото, и мы автоматически рассортируем их по альбомам</p>
        <button className="theme-toggle" onClick={toggleTheme}>
          {darkMode ? <Sun size={20} /> : <Moon size={20} />}
        </button>
      </header>

      <main className="main-content">
        <section className="upload-section">
          <div className="upload-form">
            <div className="file-input-container">
              <label className="file-input-label">
                <input
                  type="file"
                  className="file-input"
                  onChange={handleFileChange}
                  multiple
                  accept="image/*"
                />
                <span className="file-input-button">
                  <Upload size={16} /> Выбрать файлы
                </span>
                {selectedFiles.length > 0 && (
                  <span className="file-name">
                    Выбрано файлов: {selectedFiles.length}
                  </span>
                )}
              </label>
            </div>

            <div style={{ display: 'flex', gap: '1rem' }}>
              <button
                className={`upload-button ${isUploading ? 'loading' : ''}`}
                onClick={handleUpload}
                disabled={isUploading || selectedFiles.length === 0}
              >
                {isUploading ? (
                  <>
                    <span className="spinner" />
                    Загрузка...
                  </>
                ) : (
                  'Отсортировать'
                )}
              </button>

              {Object.keys(albums).length > 0 && (
                <button
                  className="upload-button"
                  onClick={handleClearAll}
                  disabled={isClearing}
                  style={{ backgroundColor: 'var(--warning-color)' }}
                >
                  {isClearing ? (
                    <>
                      <span className="spinner" />
                      Удаление...
                    </>
                  ) : (
                    <>
                      <Trash2 size={16} /> Очистить все
                    </>
                  )}
                </button>
              )}
            </div>
          </div>

          {error && <div className="error-message">{error}</div>}
        </section>

        {selectedFiles.length > 0 && (
          <section className="previews-section">
            <h3>Выбранные файлы ({selectedFiles.length})</h3>
            <div className="previews-grid">
              {selectedFiles.map((file, index) => (
                <div key={index} className="preview-item">
                  <img
                    src={URL.createObjectURL(file)}
                    alt={file.name}
                    className="preview-image"
                    onClick={() => openModal(URL.createObjectURL(file))}
                  />
                  <span className="preview-name">{file.name}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="albums-section">
          <h2>Ваши альбомы</h2>
          {Object.keys(albums).length === 0 ? (
            <p>Альбомов пока нет. Загрузите фото чтобы начать!</p>
          ) : (
            <div className="albums-container">
              {Object.entries(albums).map(([albumName, photos]) => (
                <div key={albumName} className="album-card">
                  <div className="album-header">
                    <div className="album-icon">
                      {albumName === 'Люди' ? '👥' :
                       albumName === 'Машины и транспорт' ? '🚗' :
                       albumName === 'Животные' ? '🐾' :
                       albumName === 'Природа' ? '🌿' : '📷'}
                    </div>
                    <h3 className="album-title">{albumName}</h3>
                    <div className="album-actions">
                      <span className="album-count">{photos.length} фото</span>
                      <button
                        className="download-button"
                        onClick={() => handleDownload(albumName)}
                        title="Скачать альбом"
                      >
                        <Download size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="album-photos">
                    {photos.map((photo, index) => (
                      <div key={index} className="photo-item">
                        <img
                          src={photo.url}
                          alt={photo.filename}
                          className="album-photo"
                          loading="lazy"
                          onClick={() => openModal(photo.url)}
                        />
                        <span className="photo-name">{photo.filename}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="app-footer">
        <p>© {new Date().getFullYear()} Автоматический фотоальбом</p>
      </footer>

    {/* Модальное окно (добавьте в конец компонента) */}
     {modalImage && (
  <div
    className="modal-overlay"
    onClick={closeModal}
    style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0,0,0,0.95)',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      zIndex: 9999,
      overflow: 'hidden'
    }}
  >
    <div
      className="modal-content"
      onClick={(e) => e.stopPropagation()}
      style={{
        position: 'relative',
        maxWidth: '90vw',
        maxHeight: '90vh'
      }}
    >
      {/* Улучшенная кнопка закрытия */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          closeModal();
        }}
        style={{
          position: 'absolute',
          top: '25px',
          right: '25px',
          background: 'rgba(0, 0, 0, 0.7)',
          border: '2px solid white',
          borderRadius: '50%',
          width: '50px',
          height: '50px',
          color: 'white',
          cursor: 'pointer',
          zIndex: 10000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 15px rgba(0, 0, 0, 0.7)',
          transition: 'all 0.3s ease',
          fontSize: '24px',
          fontWeight: 'bold'
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255, 0, 0, 0.8)'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(0, 0, 0, 0.7)'}
      >
        <X size={28} />
      </button>

      <img
        src={modalImage}
        alt="Просмотр фото"
        style={{
          maxHeight: '90vh',
          maxWidth: '100%',
          display: 'block',
          borderRadius: '8px',
          boxShadow: '0 0 30px rgba(0, 0, 0, 0.8)'
        }}
      />
    </div>
  </div>
)}
    </div>
  );
}

export default App;
