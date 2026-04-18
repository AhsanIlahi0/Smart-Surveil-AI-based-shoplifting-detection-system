# Smart Surveil

**Real-time Shoplifting Detection System**

Smart Surveil is a comprehensive AI-powered surveillance system designed to detect shoplifting incidents in real-time using computer vision and machine learning. The system combines a modern React frontend with a robust FastAPI backend to provide live video analysis, alert management, and comprehensive monitoring capabilities.

## 🚀 Features

### Core Functionality
- **Real-time Video Analysis**: Process uploaded videos or RTSP streams for shoplifting detection
- **Live Inference Streaming**: WebSocket-based real-time video processing with annotated frames
- **Multi-Model Support**: Support for different AI models (A, B, C) with configurable parameters
- **Alert System**: Instant notifications with sound alerts for detected incidents
- **Video Management**: Upload, process, and replay analyzed videos with incident tracking

### Dashboard Features
- **Interactive Live Feed**: Real-time video display with bounding boxes and annotations
- **Statistics Dashboard**: Comprehensive analytics with hourly/daily incident charts
- **Health Monitoring**: System status indicators for backend services and models
- **Video Library**: Browse processed videos with status tracking and metadata
- **Alert History**: Timeline of detected incidents with snapshots and details

### Technical Features
- **WebSocket Communication**: Real-time bidirectional communication for live updates
- **RESTful API**: Complete API for video management, statistics, and system control
- **Database Integration**: PostgreSQL with SQLAlchemy ORM for data persistence
- **Asynchronous Processing**: Non-blocking video processing with threading
- **Modular Architecture**: Clean separation between inference, streaming, and API layers

## 📁 Project Structure

```
smart-surveil/
├── frontend/                 # React TypeScript application
│   ├── src/
│   │   ├── routes/          # TanStack Router pages
│   │   ├── components/      # Reusable UI components
│   │   ├── lib/            # Utilities and configurations
│   │   └── styles.css      # Global styles
│   ├── package.json
│   └── vite.config.ts
├── database.py              # SQLAlchemy database configuration
├── inference.py             # AI model loading and inference
├── kaggle_client.py         # External API client (optional)
├── main.py                  # FastAPI application
├── models.py                # Database models
├── streamer.py              # Video streaming utilities
├── requirements.txt         # Python dependencies
├── setup.sh                 # Automated setup script
├── .env.example             # Environment variables template
├── models/                  # AI model files
├── uploads/                 # Uploaded video files
├── incidents/               # Processed incident data
└── README.md
```

## 📋 Prerequisites

- **Python 3.12+**
- **Node.js 18+** (for frontend development)
- **PostgreSQL 13+**
- **CUDA-compatible GPU** (recommended for faster inference)

## 🛠️ Installation

### Quick Setup (Automated)

```bash
# Run the automated setup script
./setup.sh
```

This will:
- Install and configure PostgreSQL
- Create the database and user
- Set up Python virtual environment
- Install dependencies
- Create .env file

### Manual Setup

### 2. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### 3. Database Initialization

```bash
# The application will automatically create tables on startup
# Or run manually:
python -c "from database import engine; from models import Base; Base.metadata.create_all(bind=engine)"
```

## 🚀 Running the Application

### Development Mode

1. **Start Backend**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Start Frontend** (in another terminal):
   ```bash
   cd frontend
   npm run dev
   ```

3. **Access the application**:
   - Frontend: `http://localhost:3000`
   - Backend API: `http://localhost:8000`
   - API Documentation: `http://localhost:8000/docs`

### Production Mode

```bash
# Build frontend
cd frontend && npm run build

# Start backend (serves both API and built frontend)
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 📖 API Documentation

### Core Endpoints

- `GET /` - Main dashboard (serves React app)
- `POST /api/videos/upload` - Upload video for processing
- `GET /api/videos` - List processed videos
- `GET /api/stats` - System statistics
- `POST /api/rtsp/start` - Start RTSP stream processing
- `POST /api/rtsp/stop` - Stop RTSP stream

### WebSocket Endpoints

- `ws://localhost:8000/ws/alerts` - Real-time alerts
- `ws://localhost:8000/ws/infer/{video_id}` - Video inference stream

## 🎯 Usage

### Video Upload and Analysis

1. **Upload Video**: Use the upload tab to select and upload a video file
2. **Select Model**: Choose from available AI models (A, B, or C)
3. **Start Processing**: Click "Run Inference" to begin analysis
4. **Monitor Progress**: Watch real-time processing in the live feed
5. **View Results**: Access processed video with incident annotations

### RTSP Live Streaming

1. **Enter RTSP URL**: Provide RTSP stream URL in the RTSP tab
2. **Select Model**: Choose appropriate AI model
3. **Start Stream**: Click "Start" to begin live analysis
4. **Monitor Alerts**: Receive real-time notifications of detected incidents

### System Monitoring

- **Health Status**: Check backend, database, and model status
- **Statistics**: View incident trends and system performance
- **Video Library**: Browse and replay processed videos
- **Alert History**: Review past incidents with details

## 🔧 Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://surveil_user:surveil_pass@localhost/smart_surveil

# External Services
KAGGLE_URL=https://your-kaggle-endpoint.com

# Application
SECRET_KEY=your-secret-key
DEBUG=True
```

### Model Configuration

Models are stored in the `models/` directory:
- `yolo11n.pt` - YOLOv11 nano model for object detection
- `best_attention_lstm.keras` - Custom shoplifting detection model
- `best_model.keras` - Alternative detection model

## 🧪 Testing

```bash
# Run backend tests
pytest

# Frontend testing
cd frontend && npm test

# API testing
curl http://localhost:8000/api/health
```

## 📊 Performance

- **Video Processing**: ~30 FPS on GPU, ~5 FPS on CPU
- **Real-time Streaming**: <100ms latency for WebSocket updates
- **Concurrent Streams**: Supports multiple simultaneous video analyses
- **Storage**: Efficient incident logging and video metadata management

## 🔒 Security

- Input validation for all API endpoints
- Secure file upload handling
- WebSocket connection authentication
- Environment variable configuration
- No sensitive data in logs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- YOLOv11 for object detection capabilities
- TanStack Router for frontend routing
- Radix UI for accessible components
- Chart.js for data visualization
- FastAPI for robust API framework

## 📞 Support

For questions or issues:
- Check the API documentation at `/docs`
- Review the logs in the application
- Open an issue on GitHub

---

**Smart Surveil** - Advanced AI-powered retail security solution for the modern store.
