# iPod Classic Cover Flow 实现计划

## 项目概述

本计划用于为现有系统添加一个基于 Three.js 的 iPod Classic Cover Flow 展示功能模块。该模块将作为独立子系统运行，通过 Flask Blueprint 挂载到主应用中。

---

## 一、技术架构

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      Flask Application                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  主应用蓝图  │  │ Cover Flow  │  │   其他模块蓝图       │  │
│  │   /index    │  │   /cover    │  │     /api/v1/...     │  │
│  └─────────────┘  └──────┬──────┘  └─────────────────────┘  │
│                          │                                    │
│  ┌──────────────────────┴───────────────────────────────┐  │
│  │                  CoverFlowBlueprint                      │  │
│  │   - /cover           入口页面                            │  │
│  │   - /cover/api/list  获取专辑列表                        │  │
│  │   - /cover/api/detail/<id>  获取专辑详情                 │  │
│  │   - /cover/api/track/<id>   获取曲目信息                  │  │
│  └──────────────────────┬─────────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────────┐
│                  Three.js 渲染层                             │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │                   CoverFlowScene                        │  │
│  │                                                        │  │
│  │   Camera  ←─────────────────────→  AlbumStack          │  │
│  │   PerspectiveCamera               AlbumCover[]         │  │
│  │                                      - Mesh           │  │
│  │   Controls ←─────────────────────→  - PlaneGeometry    │  │
│  │   CustomOrbitControls              - TextureLoader    │  │
│  │                                      - Raycaster      │  │
│  │   AnimationLoop ←────────────────→  - ShaderMaterial   │  │
│  │   requestAnimationFrame                                │  │
│  │   easingFunction                                    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 目录结构

```
系统部署/
├── docs/
│   └── cover-flow-implementation-plan.md   ← 本文档
├── cover-flow/
│   ├── __init__.py                          ← Blueprint 注册
│   ├── routes.py                            ← API 路由定义
│   ├── data/
│   │   └── albums.json                      ← 示例专辑数据
│   └── static/
│       ├── cover-flow.js                    ← Three.js 主模块
│       ├── shaders/
│       │   ├── cover.vert                   ← 顶点着色器
│       │   └── cover.frag                   ← 片段着色器
│       └── styles/
│           └── cover-flow.css               ← 样式文件
└── templates/
    └── cover-flow/
        └── index.html                       ← 渲染模板
```

---

## 二、路由设计

### 2.1 Flask Blueprint 配置

```python
# cover_flow/__init__.py
from flask import Blueprint

cover_flow_bp = Blueprint(
    'cover_flow',
    __name__,
    url_prefix='/cover',
    template_folder='../templates/cover-flow',
    static_folder='static',
    static_url_path='/static/cover-flow'
)

from . import routes
```

### 2.2 API 端点定义

```
GET  /cover                          → 渲染主页面
GET  /cover/api/list                → 获取专辑列表
     Query: page=1&limit=20&sort=recent

GET  /cover/api/detail/<album_id>   → 获取专辑详情
     Response: {
       "id": "alb_001",
       "title": "Album Title",
       "artist": "Artist Name",
       "year": 2008,
       "cover_url": "/static/covers/alb_001.jpg",
       "tracks": [...]
     }

GET  /cover/api/track/<track_id>    → 获取曲目信息
     Response: {
       "id": "trk_001",
       "title": "Track Title",
       "duration": 245,
       "album_id": "alb_001",
       "track_number": 1
     }
```

---

## 三、Three.js 实现细节

### 3.1 核心类设计

```javascript
// cover-flow/static/cover-flow.js

class CoverFlowManager {
    constructor(container) {
        this.container = container;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.albums = [];
        this.currentIndex = 0;
        this.targetIndex = 0;
        this.isAnimating = false;
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
    }

    init() {
        this.setupScene();
        this.setupCamera();
        this.setupRenderer();
        this.setupLights();
        this.setupControls();
        this.loadAlbums();
        this.setupEventListeners();
        this.animate();
    }

    setupScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x000000);
        this.scene.fog = new THREE.Fog(0x000000, 5, 20);
    }

    setupCamera() {
        const aspect = window.innerWidth / window.innerHeight;
        this.camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 1000);
        this.camera.position.set(0, 0, 10);
    }

    setupRenderer() {
        this.renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: true
        });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.container.appendChild(this.renderer.domElement);
    }

    setupLights() {
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
        this.scene.add(ambientLight);

        const spotLight = new THREE.SpotLight(0xffffff, 1);
        spotLight.position.set(0, 5, 10);
        spotLight.angle = Math.PI / 6;
        this.scene.add(spotLight);
    }

    loadAlbums() {
        // 动态加载专辑纹理并创建封面网格
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        this.updateCameraPosition();
        this.renderer.render(this.scene, this.camera);
    }

    updateCameraPosition() {
        // 实现 Cover Flow 视角平滑过渡
    }
}
```

### 3.2 封面布局算法

```
当前选中专辑位于 z=0 平面，x=0
左侧专辑沿 -X 轴方向依次排列，角度偏移 +Z 轴旋转
右侧专辑沿 +X 轴方向依次排列，角度偏移 -Z 轴旋转

偏移公式:
  offsetX = (index - currentIndex) * spacing
  offsetZ = -|offsetX| * 0.5
  rotationY = (index - currentIndex) * maxAngle
           = (index - currentIndex) * (π / 6)   // 30度
```

```javascript
// 封面位置计算
calculateAlbumPosition(index) {
    const spacing = 1.8;        // 封面间距
    const maxAngle = Math.PI / 6;  // 最大旋转角度 30°

    const offsetX = (index - this.currentIndex) * spacing;
    const offsetZ = -Math.abs(offsetX) * 0.5;  // 深度凹陷效果
    const rotationY = -Math.sign(offsetX) * Math.min(Math.abs(offsetX) * 0.15, maxAngle);

    return new THREE.Vector3(offsetX, 0, offsetZ + 3);
}

calculateAlbumRotation(index) {
    const maxAngle = Math.PI / 6;
    const offsetX = (index - this.currentIndex) * 1.8;
    return new THREE.Euler(0, -Math.sign(offsetX) * Math.min(Math.abs(offsetX) * 0.15, maxAngle), 0);
}
```

### 3.3 着色器实现

```glsl
// cover-flow/static/shaders/cover.vert
varying vec2 vUv;
varying vec3 vNormal;

void main() {
    vUv = uv;
    vNormal = normalMatrix * normal;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
```

```glsl
// cover-flow/static/shaders/cover.frag
uniform sampler2D coverTexture;
uniform float highlight;
uniform float glossiness;

varying vec2 vUv;
varying vec3 vNormal;

void main() {
    vec4 texColor = texture2D(coverTexture, vUv);

    // 高光反射模拟
    vec3 viewDir = vec3(0.0, 0.0, 1.0);
    float spec = pow(max(dot(vNormal, viewDir), 0.0), 32.0) * glossiness;

    // 边缘光晕
    float edge = 1.0 - smoothstep(0.3, 0.5, abs(vUv.x - 0.5) + abs(vUv.y - 0.5));

    vec3 finalColor = texColor.rgb * (0.9 + 0.1 * highlight) + vec3(spec);

    gl_FragColor = vec4(finalColor, 1.0);
}
```

---

## 四、数据模型

### 4.1 专辑数据 JSON 结构

```json
{
  "albums": [
    {
      "id": "alb_001",
      "title": "Abbey Road",
      "artist": "The Beatles",
      "year": 1969,
      "genre": "Rock",
      "cover_url": "/static/covers/abbey-road.jpg",
      "tracks": [
        {
          "id": "trk_001",
          "title": "Come Together",
          "duration": 259,
          "track_number": 1
        }
      ]
    }
  ]
}
```

### 4.2 封面纹理加载策略

```javascript
// 使用 Three.js LoadingManager 管理纹理加载
const textureLoader = new THREE.TextureLoader();
const loadingManager = new THREE.LoadingManager();

loadingManager.onProgress = (url, loaded, total) => {
    const progress = (loaded / total) * 100;
    this.updateLoadingProgress(progress);
};

this.albums.forEach((album, index) => {
    textureLoader.load(
        album.cover_url,
        (texture) => {
            texture.minFilter = THREE.LinearFilter;
            texture.magFilter = THREE.LinearFilter;
            this.createAlbumMesh(album, texture, index);
        },
        undefined,
        (error) => {
            console.error(`Failed to load texture: ${album.cover_url}`, error);
            this.createFallbackCover(album, index);
        }
    );
});
```

---

## 五、交互动效

### 5.1 键盘导航

```javascript
setupKeyboardControls() {
    document.addEventListener('keydown', (e) => {
        switch(e.key) {
            case 'ArrowLeft':
                this.previousAlbum();
                break;
            case 'ArrowRight':
                this.nextAlbum();
                break;
            case 'Enter':
                this.selectCurrentAlbum();
                break;
            case 'Escape':
                this.closeDetail();
                break;
        }
    });
}

previousAlbum() {
    if (this.targetIndex > 0 && !this.isAnimating) {
        this.targetIndex--;
        this.animateToIndex(this.targetIndex);
    }
}

nextAlbum() {
    if (this.targetIndex < this.albums.length - 1 && !this.isAnimating) {
        this.targetIndex++;
        this.animateToIndex(this.targetIndex);
    }
}
```

### 5.2 平滑过渡动画

```javascript
// 使用 GSAP 或 TWEEN.js 实现流畅动画
import TWEEN from '@tweenjs/tween.js';

animateToIndex(targetIndex) {
    this.isAnimating = true;

    const startValues = {
        x: this.camera.position.x,
        y: this.camera.position.y,
        z: this.camera.position.z
    };

    const targetX = 0;
    const targetY = 0;
    const targetZ = 10;

    new TWEEN.Tween(startValues)
        .to({ x: targetX, y: targetY, z: targetZ }, 600)
        .easing(TWEEN.Easing.Cubic.Out)
        .onUpdate(() => {
            this.camera.position.x = startValues.x;
            this.camera.position.y = startValues.y;
            this.camera.position.z = startValues.z;
        })
        .onComplete(() => {
            this.currentIndex = targetIndex;
            this.isAnimating = false;
            this.onIndexChanged(targetIndex);
        })
        .start();
}
```

### 5.3 鼠标拖拽旋转

```javascript
setupDragControls() {
    let isDragging = false;
    let startX = 0;
    let currentRotation = 0;

    this.renderer.domElement.addEventListener('mousedown', (e) => {
        isDragging = true;
        startX = e.clientX;
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;

        const deltaX = e.clientX - startX;
        currentRotation = deltaX * 0.005;

        // 实时更新所有封面角度
        this.albums.forEach((album, index) => {
            const baseRotation = (index - this.currentIndex) * Math.PI / 6;
            album.mesh.rotation.y = baseRotation + currentRotation;
        });
    });

    document.addEventListener('mouseup', (e) => {
        if (!isDragging) return;
        isDragging = false;

        const deltaX = e.clientX - startX;
        if (Math.abs(deltaX) > 50) {
            if (deltaX > 0) {
                this.previousAlbum();
            } else {
                this.nextAlbum();
            }
        }
    });
}
```

---

## 六、性能优化

### 6.1 渲染优化策略

```
1. 纹理优化
   - 使用 512x512 分辨率的缩略图用于 Cover Flow
   - 启用纹理压缩 (KTX2 / Basis Universal)
   - 使用 Mipmap 减少远距离采样

2. 几何体优化
   - 使用 PlaneGeometry 替代复杂几何体
   - 实例化渲染 (InstancedMesh) 用于大量封面
   - 视锥体剔除 (Frustum Culling)

3. 着色器优化
   - 避免在片段着色器中进行分支判断
   - 使用 uniforms 缓存计算结果
   - 减少纹理采样次数
```

```javascript
// 启用实例化渲染
const instancedMesh = new THREE.InstancedMesh(
    geometry,
    material,
    albumCount
);

const dummy = new THREE.Object3D();
albums.forEach((album, i) => {
    dummy.position.copy(album.position);
    dummy.rotation.copy(album.rotation);
    dummy.updateMatrix();
    instancedMesh.setMatrixAt(i, dummy.matrix);
});
```

### 6.2 懒加载策略

```javascript
// 只加载视口内可见的封面 + 两侧各 3 张预加载
const VISIBLE_RANGE = 3;

loadVisibleAlbums(currentIndex) {
    const start = Math.max(0, currentIndex - VISIBLE_RANGE);
    const end = Math.min(this.albums.length, currentIndex + VISIBLE_RANGE);

    for (let i = start; i < end; i++) {
        if (!this.albums[i].isLoaded) {
            this.loadAlbumTexture(i);
        }
    }
}
```

### 6.3 帧率控制

```javascript
// 根据设备性能自适应帧率
class AdaptiveFrameRate {
    constructor() {
        this.targetFPS = 60;
        this.frameInterval = 1000 / this.targetFPS;
        this.lastTime = 0;
        this.frames = 0;
        this.fps = 60;
    }

    shouldRender(currentTime) {
        this.frames++;
        if (currentTime >= this.lastTime + 1000) {
            this.fps = this.frames;
            this.frames = 0;
            this.lastTime = currentTime;

            // 如果 FPS 过低，降低渲染质量
            if (this.fps < 30) {
                this.reduceQuality();
            }
        }

        return currentTime - this.lastTime >= this.frameInterval;
    }
}
```

---

## 七、部署步骤

### 7.1 文件创建顺序

```
Step 1: 创建目录结构
  └─ mkdir -p cover-flow/{data,static/{shaders,styles},templates/cover-flow}

Step 2: 创建数据文件
  └─ cover-flow/data/albums.json

Step 3: 创建 Python 后端
  ├─ cover-flow/__init__.py
  └─ cover-flow/routes.py

Step 4: 创建前端资源
  ├─ cover-flow/static/cover-flow.js
  ├─ cover-flow/static/shaders/cover.vert
  ├─ cover-flow/static/shaders/cover.frag
  └─ cover-flow/static/styles/cover-flow.css

Step 5: 创建模板
  └─ cover-flow/templates/cover-flow/index.html

Step 6: 注册 Blueprint
  └─ 修改主应用 app.py
```

### 7.2 Blueprint 注册代码

```python
# app.py (主应用)
from cover_flow import cover_flow_bp

def create_app():
    app = Flask(__name__)

    # 注册 Cover Flow Blueprint
    app.register_blueprint(cover_flow_bp)

    return app
```

### 7.3 验证检查清单

- [ ] Flask Blueprint 正确注册，访问 `/cover` 返回 HTML 页面
- [ ] API 端点 `/cover/api/list` 返回 JSON 数据
- [ ] Three.js 场景正确初始化，无 WebGL 错误
- [ ] 封面网格正确渲染，纹理加载成功
- [ ] 键盘左右箭头可切换专辑
- [ ] 鼠标拖拽可旋转封面视角
- [ ] 动画过渡流畅，无卡顿
- [ ] 响应式布局适配不同屏幕尺寸
- [ ] 控制台无 Error 级别日志
- [ ] 移动端触摸滑动正常工作

---

## 八、依赖项

### 8.1 Python 依赖

```
flask>=2.3.0
flask-cors>=4.0.0
```

### 8.2 前端依赖 (CDN)

```
three.js:         https://unpkg.com/three@0.160.0/build/three.module.js
@three/examples:  https://unpkg.com/three@0.160.0/examples/jsm/
tween.js:         https://unpkg.com/@tweenjs/tween.js@23.1.1/dist/tween.esm.js
```

### 8.3 可选依赖 (构建时)

```
# npm 依赖 (用于打包)
npm install three @tweenjs/tween.js
npm install --save-dev vite @vitejs/plugin-glsl
```

---

## 九、预期效果

### 9.1 视觉呈现

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│                        Cover Flow                           │
│                                                              │
│                    ┌─────────┐                               │
│          ┌───┐     │ ╔═══╗   │     ┌───┐                    │
│    ┌───┐ │   │     │ ║   ║   │     │   │ ┌───┐              │
│    │   │ │ A │     │ ║ B ║   │     │ C │ │   │              │
│    │   │ │   │     │ ║   ║   │     │   │ │ D │              │
│    └───┘ └───┘     │ ╚═══╝   │     └───┘ └───┘              │
│   Album A         Album B       Album C    Album D          │
│   (rotated)       (center)      (rotated)                   │
│                                                              │
│  ← [ 1 / 42 ] →                                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 9.2 交互效果描述

```
1. 默认状态
   - 封面以半圆弧形排列
   - 选中封面居中显示，正对镜头
   - 左右封面依次向远处凹陷，角度递增

2. 切换动画 (600ms)
   - 相机平滑移动到新位置
   - 封面沿弧形轨道滑动
   - 透明度渐变反映前后位置

3. 高亮状态
   - 当前选中封面轻微放大 (scale 1.05)
   - 边缘添加光晕效果
   - 高光反射增强

4. 悬停反馈
   - 封面轻微前移
   - 阴影加深
   - 标题信息浮现
```

---

## 十、后续扩展

### 10.1 可选功能

```
1. 3D 专辑旋转查看
   - 鼠标悬停时封面自动旋转
   - 360° 全方位展示专辑封面

2. 曲目播放集成
   - 点击封面播放该专辑第一首曲目
   - 底部显示播放进度条
   - 曲目切换时专辑轻微浮动

3. 搜索与筛选
   - 按专辑名、艺术家、流派搜索
   - 筛选结果动态更新 Cover Flow

4. 分享功能
   - 生成当前专辑的分享链接
   - 支持社交媒体分享卡片

5. 历史记录
   - 记录用户浏览历史
   - 快速访问最近查看的专辑
```

### 10.2 性能监控

```javascript
// 添加性能监控
const stats = new Stats();
stats.showPanel(0); // FPS panel
document.body.appendChild(stats.dom);

function animate() {
    stats.begin();

    // 渲染逻辑
    this.renderer.render(this.scene, this.camera);

    stats.end();
    requestAnimationFrame(() => this.animate());
}
```

---

*文档版本: 1.0*
*创建日期: 2026-04-05*
*维护者: Development Team*
