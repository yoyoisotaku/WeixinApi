# 微信小程序 + H5（web-view）腿部接球示例

这个仓库现在包含一个**轻量级方案**：
- 小程序负责首页、开始页、结果页。
- 真正的小游戏逻辑放在 `web-view` 里的 H5 页面。
- H5 使用摄像头 + MediaPipe Pose Landmarker（Web）进行单人姿态识别。
- 业务只关注下半身关键点（左/右髋、膝、踝），进行掉落球接球判定。

## 目录结构

```text
miniprogram/
  app.js
  app.json
  app.wxss
  pages/
    home/      # 首页
    start/     # web-view 承载页
    result/    # 结果页
h5/
  index.html   # 游戏主体页面
```

## 对应目标说明

1. **小程序首页/开始页/结果页**：已完成（`miniprogram/pages/*`）。
2. **H5 调用摄像头实时画面**：`getUserMedia` + `<video>` 完成。
3. **MediaPipe Pose Landmarker for Web**：通过 `@mediapipe/tasks-vision` CDN 初始化 `PoseLandmarker`。
4. **仅使用下半身关键点**：只读取 index `23/24/25/26/27/28`（髋膝踝）。
5. **顶部随机掉球**：`randomBall()` 从顶部生成。
6. **腿部命中+上抬趋势判定**：球进入腿部包围框且踝点上抬速度超过阈值视为成功。
7. **成功后反弹+加分+combo**：命中后反弹、增加分数与连击。
8. **20 秒结束并回传分数**：超时后 `wx.miniProgram.postMessage({ type: 'GAME_OVER', ... })`。
9. **轻量方案**：无 3D AR、无 SLAM、无平面检测、无空间锚点。
10. **优先微信内性能**：
   - `pose_landmarker_lite` 模型；
   - 单人识别 `numPoses: 1`；
   - 视频目标 640x480 / 30fps。

## 接入方式（关键）

1. 将 `h5/index.html` 部署到**HTTPS 静态域名**（例如 COS/OSS + CDN）。
2. 在小程序后台把该域名加入 `业务域名`（web-view 访问白名单）。
3. 修改 `miniprogram/pages/start/start.js` 中的：

```js
const DEFAULT_GAME_URL = 'https://your-static-domain.example.com/h5/index.html';
```

4. 用微信开发者工具导入 `miniprogram` 目录并运行。

## 兼容与性能建议

- 建议 iOS/Android 微信较新版本，允许摄像头权限。
- 如果 GPU delegate 在部分机型不稳定，可在 H5 中改为 CPU delegate。
- 若性能紧张，可进一步降低视频分辨率或减少绘制效果。
