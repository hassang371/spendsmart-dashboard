export const ASSET_MAP = {
  lottie: {
    rocket: '/slush/67fec9c2e7d76beccecdd1cf_GetStashed - Onboarding - Icon Rocket - V01.json',
    smiley: '/slush/icon-smiley.json',
    wallet: '/slush/67fec9c215412ef64f152118_GetStashed - Onboarding - Icon Wallet - V01.json',
    coin: '/slush/67fec9c205180e5c013941f7_GetStashed - Onboarding - Icon Coin - V01.json',
    yellowCoin: '/slush/69397ea95043b60abd607e1c_Slush - Coin Illustration - Yellow - V01.json',
    cards: '/slush/icon-cards.json',
    devices: '/slush/icon-devices.json',
    avatar: '/slush/67fec9c2e7d76beccecdd1b6_GetStashed - Onboarding - Icon Avatar - V01.json',
    approved: '/slush/67fec9c205180e5c01394200_GetStashed - Onboarding - Icon Approved - V01.json',
    plane: '/slush/67fec9c2233ed64fe7d7a760_GetStashed - Onboarding - Icon Plane - V02.json',
    like: '/slush/67fec9c245cbd3021d9fe63d_GetStashed - Onboarding - Icon Like - V01.json',
    keys: '/slush/67fec9c24f08f341a2cf5806_GetStashed - Onboarding - Icon Keys - V01.json',
    codeLock: '/slush/67fec9c284a87cc8c073d98e_GetStashed - Onboarding - Icon Code Lock - V01.json',
  },
  video: {
    hero: '/slush/hero-video.mp4',
  },
  images: {
    opengraph: '/slush/6870e4e53832c8115a855885_slush_opengraph.jpg',
    logoBlue3D: '/slush/6870becddb972b0b143dfe65_Slush_Logo_3D_Blue.avif',
    browserChrome: '/slush/680905cfdc450738383648f3_icon-chrome.png',
    browserIOS: '/slush/680905cfdc450738383648f4_icon-ios.png',
    browserEdge: '/slush/680905cfdc4507383836496e_logo-ie.svg',
    browserBrave: '/slush/680905cfdc4507383836496f_logo-brave.svg',
    browserArc: '/slush/680905cfdc45073838364970_logo-arc.svg',
    browserAndroid: '/slush/680905cfdc45073838364972_logo-android.svg',
    qrCode: '/slush/680905cfdc45073838364990_slush-download-qr.png',
  },
};

/**
 * Map Webflow CDN URLs to local asset paths
 */
export const CDN_TO_LOCAL_MAP: Record<string, string> = {
  // Video
  'https://sui-dev.b-cdn.net/SuiPlay/Slush%20-%20WEBSITE%20VIDEO%20-%20V03-hevc-safari.mp4': '/slush/hero-video.mp4',

  // Lottie Animations
  'https://cdn.prod.website-files.com/67d9fcb123f67f0f34dd8fd1/67fec9c2e7d76beccecdd1cf_GetStashed%20-%20Onboarding%20-%20Icon%20Rocket%20-%20V01.json': '/slush/rocket.json',
  'https://cdn.prod.website-files.com/67d9fcb123f67f0f34dd8fd1/67fec9c215412ef64f152118_GetStashed%20-%20Onboarding%20-%20Icon%20Wallet%20-%20V01.json': '/slush/wallet.json',
  'https://cdn.prod.website-files.com/67d9fcb123f67f0f34dd8fd1/67fec9c205180e5c013941f7_GetStashed%20-%20Onboarding%20-%20Icon%20Coin%20-%20V01.json': '/slush/coin.json',

  // Open Graph
  'https://cdn.prod.website-files.com/680905cfdc450738383648a6/6870e4e53832c8115a855885_slush_opengraph.jpg': '/slush/6870e4e53832c8115a855885_slush_opengraph.jpg',

  // Hero background
  'https://cdn.prod.website-files.com/680905cfdc450738383648a6/6870becddb972b0b143dfe65_Slush_Logo_3D_Blue.avif': '/slush/6870becddb972b0b143dfe65_Slush_Logo_3D_Blue.avif',
};
