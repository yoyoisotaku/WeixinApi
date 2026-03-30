const DEFAULT_GAME_URL = 'https://your-static-domain.example.com/h5/index.html';

Page({
  data: {
    gameUrl: ''
  },

  onLoad() {
    const url = `${DEFAULT_GAME_URL}?source=miniprogram&v=1`;
    this.setData({ gameUrl: url });
  },

  onGameMessage(event) {
    const payload = (event.detail.data || []).slice(-1)[0] || {};
    if (payload.type !== 'GAME_OVER') {
      return;
    }

    const app = getApp();
    app.globalData.latestScore = payload.score || 0;
    app.globalData.latestCombo = payload.maxCombo || 0;
    app.globalData.latestCatchCount = payload.catchCount || 0;

    wx.redirectTo({
      url: `/pages/result/result?score=${payload.score || 0}&maxCombo=${payload.maxCombo || 0}&catchCount=${payload.catchCount || 0}`
    });
  }
});
