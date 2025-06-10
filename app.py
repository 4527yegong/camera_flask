from flask import Flask, Response, render_template, jsonify
import cv2
import base64
import numpy as np
from queue import Queue
import threading
import os
from datetime import datetime

app = Flask(__name__)

# 摄像头配置
CAMERA_IP = '192.168.10.66'
CAMERA_USER = 'admin'
CAMERA_PASS = 'root147258'

# 视频流配置
FRAME_INTERVAL = 0.04  # 限制帧率约为25fps
JPEG_QUALITY = 70     # JPEG压缩质量
FRAME_WIDTH = 640     # 帧宽度
FRAME_HEIGHT = 480    # 帧高度

# 创建帧缓冲队列
frame_buffer = Queue(maxsize=2)  # 限制缓冲区大小为2帧

def capture_frames():
    """后台线程持续捕获视频帧"""
    cap = cv2.VideoCapture(f'rtsp://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}/Streaming/Channels/1')

    # 设置摄像头参数
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 最小化缓冲

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 调整图像大小
        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

        # 转换为JPEG格式，控制质量
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        _, buffer = cv2.imencode('.jpg', frame, encode_param)

        # 更新缓冲区，如果满了就丢弃旧帧
        if frame_buffer.full():
            try:
                frame_buffer.get_nowait()
            except:
                pass
        frame_buffer.put(buffer.tobytes())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    def generate_frames():
        while True:
            # 从缓冲区获取最新帧
            frame = frame_buffer.get()

            # 生成MJPEG流
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')



@app.route('/save_snapshot', methods=['POST'])
def save_snapshot():
    try:
        # 获取当前帧
        if not frame_buffer.empty():
            frame_data = frame_buffer.get()
            
            # 确保static目录存在
            if not os.path.exists('static'):
                os.makedirs('static')
                
            # 生成唯一的文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'snapshot_{timestamp}.jpg'
            filepath = os.path.join('static', filename)
            
            # 保存图片文件
            with open(filepath, 'wb') as f:
                f.write(frame_data)
                
            return jsonify({
                'success': True,
                'image': f'/static/{filename}'

            })
            
        return jsonify({
            'success': False,
            'error': '没有可用的视频帧'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    # 启动帧捕获线程
    threading.Thread(target=capture_frames, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, threaded=True)