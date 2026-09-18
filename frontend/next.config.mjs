/** @type {import('next').NextConfig} */
const nextConfig = {
  // 사내 서버에 단독 배포하기 좋게 standalone 으로 빌드합니다.
  output: "standalone",
};
export default nextConfig;
