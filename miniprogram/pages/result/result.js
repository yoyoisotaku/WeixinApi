Page({
  data: {
    score: 0,
    maxCombo: 0,
    catchCount: 0
  },

  onLoad(query) {
    const app = getApp();
    this.setData({
      score: Number(query.score || app.globalData.latestScore || 0),
      maxCombo: Number(query.maxCombo || app.globalData.latestCombo || 0),
      catchCount: Number(query.catchCount || app.globalData.latestCatchCount || 0)
    });
  },

  playAgain() {
    wx.redirectTo({
      url: '/pages/start/start'
    });
  },

  goHome() {
    wx.reLaunch({
      url: '/pages/home/home'
    });
  }
});
