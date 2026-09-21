// 세계 시계가 아는 도시 목록.
//
// 같은 목록이 "도구 모음" 앱(official_apps/toolbox/server.py)에도 있습니다.
// 도커 빌드 범위가 서로 달라서 파일 하나를 같이 쓰지는 못하고,
// official_apps/tests/test_city_zones.py 가 두 목록이 어긋나면 알려 줍니다.
// 도시를 더할 때는 이 파일과 server.py 를 같이 고쳐 주세요.

export type City = {
  /** 화면에 보이는 이름 */
  name: string;
  /** 영문 이름. 영어로 쳐도 찾히게 합니다 */
  en: string;
  /** 나라(또는 지역). 나라 이름으로도 찾히게 합니다 */
  country: string;
  /** 표준 시간대 이름 */
  zone: string;
};

export const CITIES: City[] = [
  // 한국
  { name: "서울", en: "Seoul", country: "한국", zone: "Asia/Seoul" },
  { name: "수원", en: "Suwon", country: "한국", zone: "Asia/Seoul" },
  { name: "기흥", en: "Giheung", country: "한국", zone: "Asia/Seoul" },
  { name: "화성", en: "Hwaseong", country: "한국", zone: "Asia/Seoul" },
  { name: "평택", en: "Pyeongtaek", country: "한국", zone: "Asia/Seoul" },
  { name: "천안", en: "Cheonan", country: "한국", zone: "Asia/Seoul" },
  { name: "아산", en: "Asan", country: "한국", zone: "Asia/Seoul" },
  { name: "구미", en: "Gumi", country: "한국", zone: "Asia/Seoul" },
  { name: "광주", en: "Gwangju", country: "한국", zone: "Asia/Seoul" },
  { name: "대전", en: "Daejeon", country: "한국", zone: "Asia/Seoul" },
  { name: "대구", en: "Daegu", country: "한국", zone: "Asia/Seoul" },
  { name: "부산", en: "Busan", country: "한국", zone: "Asia/Seoul" },
  { name: "제주", en: "Jeju", country: "한국", zone: "Asia/Seoul" },

  // 일본
  { name: "도쿄", en: "Tokyo", country: "일본", zone: "Asia/Tokyo" },
  { name: "오사카", en: "Osaka", country: "일본", zone: "Asia/Tokyo" },
  { name: "나고야", en: "Nagoya", country: "일본", zone: "Asia/Tokyo" },
  { name: "요코하마", en: "Yokohama", country: "일본", zone: "Asia/Tokyo" },
  { name: "후쿠오카", en: "Fukuoka", country: "일본", zone: "Asia/Tokyo" },
  { name: "삿포로", en: "Sapporo", country: "일본", zone: "Asia/Tokyo" },

  // 중국·대만·홍콩
  { name: "베이징", en: "Beijing", country: "중국", zone: "Asia/Shanghai" },
  { name: "상하이", en: "Shanghai", country: "중국", zone: "Asia/Shanghai" },
  { name: "시안", en: "Xian", country: "중국", zone: "Asia/Shanghai" },
  { name: "톈진", en: "Tianjin", country: "중국", zone: "Asia/Shanghai" },
  { name: "쑤저우", en: "Suzhou", country: "중국", zone: "Asia/Shanghai" },
  { name: "선전", en: "Shenzhen", country: "중국", zone: "Asia/Shanghai" },
  { name: "광저우", en: "Guangzhou", country: "중국", zone: "Asia/Shanghai" },
  { name: "칭다오", en: "Qingdao", country: "중국", zone: "Asia/Shanghai" },
  { name: "청두", en: "Chengdu", country: "중국", zone: "Asia/Shanghai" },
  { name: "홍콩", en: "Hong Kong", country: "홍콩", zone: "Asia/Hong_Kong" },
  { name: "타이베이", en: "Taipei", country: "대만", zone: "Asia/Taipei" },
  { name: "신주", en: "Hsinchu", country: "대만", zone: "Asia/Taipei" },

  // 동남아시아
  { name: "호치민", en: "Ho Chi Minh City", country: "베트남", zone: "Asia/Ho_Chi_Minh" },
  { name: "하노이", en: "Hanoi", country: "베트남", zone: "Asia/Ho_Chi_Minh" },
  { name: "박닌", en: "Bac Ninh", country: "베트남", zone: "Asia/Ho_Chi_Minh" },
  { name: "타이응우옌", en: "Thai Nguyen", country: "베트남", zone: "Asia/Ho_Chi_Minh" },
  { name: "방콕", en: "Bangkok", country: "태국", zone: "Asia/Bangkok" },
  { name: "싱가포르", en: "Singapore", country: "싱가포르", zone: "Asia/Singapore" },
  { name: "쿠알라룸푸르", en: "Kuala Lumpur", country: "말레이시아", zone: "Asia/Kuala_Lumpur" },
  { name: "자카르타", en: "Jakarta", country: "인도네시아", zone: "Asia/Jakarta" },
  { name: "마닐라", en: "Manila", country: "필리핀", zone: "Asia/Manila" },
  { name: "프놈펜", en: "Phnom Penh", country: "캄보디아", zone: "Asia/Phnom_Penh" },
  { name: "양곤", en: "Yangon", country: "미얀마", zone: "Asia/Yangon" },

  // 남아시아
  { name: "델리", en: "Delhi", country: "인도", zone: "Asia/Kolkata" },
  { name: "노이다", en: "Noida", country: "인도", zone: "Asia/Kolkata" },
  { name: "구르가온", en: "Gurgaon", country: "인도", zone: "Asia/Kolkata" },
  { name: "벵갈루루", en: "Bengaluru", country: "인도", zone: "Asia/Kolkata" },
  { name: "첸나이", en: "Chennai", country: "인도", zone: "Asia/Kolkata" },
  { name: "뭄바이", en: "Mumbai", country: "인도", zone: "Asia/Kolkata" },
  { name: "하이데라바드", en: "Hyderabad", country: "인도", zone: "Asia/Kolkata" },
  { name: "콜카타", en: "Kolkata", country: "인도", zone: "Asia/Kolkata" },
  { name: "다카", en: "Dhaka", country: "방글라데시", zone: "Asia/Dhaka" },
  { name: "콜롬보", en: "Colombo", country: "스리랑카", zone: "Asia/Colombo" },
  { name: "카라치", en: "Karachi", country: "파키스탄", zone: "Asia/Karachi" },
  { name: "이슬라마바드", en: "Islamabad", country: "파키스탄", zone: "Asia/Karachi" },

  // 중앙아시아·러시아
  { name: "타슈켄트", en: "Tashkent", country: "우즈베키스탄", zone: "Asia/Tashkent" },
  { name: "알마티", en: "Almaty", country: "카자흐스탄", zone: "Asia/Almaty" },
  { name: "블라디보스토크", en: "Vladivostok", country: "러시아", zone: "Asia/Vladivostok" },
  { name: "노보시비르스크", en: "Novosibirsk", country: "러시아", zone: "Asia/Novosibirsk" },
  { name: "모스크바", en: "Moscow", country: "러시아", zone: "Europe/Moscow" },
  { name: "상트페테르부르크", en: "Saint Petersburg", country: "러시아", zone: "Europe/Moscow" },

  // 중동·아프리카
  { name: "두바이", en: "Dubai", country: "아랍에미리트", zone: "Asia/Dubai" },
  { name: "아부다비", en: "Abu Dhabi", country: "아랍에미리트", zone: "Asia/Dubai" },
  { name: "도하", en: "Doha", country: "카타르", zone: "Asia/Qatar" },
  { name: "리야드", en: "Riyadh", country: "사우디아라비아", zone: "Asia/Riyadh" },
  { name: "제다", en: "Jeddah", country: "사우디아라비아", zone: "Asia/Riyadh" },
  { name: "쿠웨이트", en: "Kuwait City", country: "쿠웨이트", zone: "Asia/Kuwait" },
  { name: "테헤란", en: "Tehran", country: "이란", zone: "Asia/Tehran" },
  { name: "텔아비브", en: "Tel Aviv", country: "이스라엘", zone: "Asia/Jerusalem" },
  { name: "이스탄불", en: "Istanbul", country: "튀르키예", zone: "Europe/Istanbul" },
  { name: "카이로", en: "Cairo", country: "이집트", zone: "Africa/Cairo" },
  { name: "나이로비", en: "Nairobi", country: "케냐", zone: "Africa/Nairobi" },
  { name: "라고스", en: "Lagos", country: "나이지리아", zone: "Africa/Lagos" },
  { name: "요하네스버그", en: "Johannesburg", country: "남아프리카공화국", zone: "Africa/Johannesburg" },
  { name: "카사블랑카", en: "Casablanca", country: "모로코", zone: "Africa/Casablanca" },

  // 유럽
  { name: "런던", en: "London", country: "영국", zone: "Europe/London" },
  { name: "더블린", en: "Dublin", country: "아일랜드", zone: "Europe/Dublin" },
  { name: "리스본", en: "Lisbon", country: "포르투갈", zone: "Europe/Lisbon" },
  { name: "파리", en: "Paris", country: "프랑스", zone: "Europe/Paris" },
  { name: "프랑크푸르트", en: "Frankfurt", country: "독일", zone: "Europe/Berlin" },
  { name: "베를린", en: "Berlin", country: "독일", zone: "Europe/Berlin" },
  { name: "뮌헨", en: "Munich", country: "독일", zone: "Europe/Berlin" },
  { name: "암스테르담", en: "Amsterdam", country: "네덜란드", zone: "Europe/Amsterdam" },
  { name: "브뤼셀", en: "Brussels", country: "벨기에", zone: "Europe/Brussels" },
  { name: "마드리드", en: "Madrid", country: "스페인", zone: "Europe/Madrid" },
  { name: "바르셀로나", en: "Barcelona", country: "스페인", zone: "Europe/Madrid" },
  { name: "로마", en: "Rome", country: "이탈리아", zone: "Europe/Rome" },
  { name: "밀라노", en: "Milan", country: "이탈리아", zone: "Europe/Rome" },
  { name: "취리히", en: "Zurich", country: "스위스", zone: "Europe/Zurich" },
  { name: "제네바", en: "Geneva", country: "스위스", zone: "Europe/Zurich" },
  { name: "빈", en: "Vienna", country: "오스트리아", zone: "Europe/Vienna" },
  { name: "프라하", en: "Prague", country: "체코", zone: "Europe/Prague" },
  { name: "부다페스트", en: "Budapest", country: "헝가리", zone: "Europe/Budapest" },
  { name: "바르샤바", en: "Warsaw", country: "폴란드", zone: "Europe/Warsaw" },
  { name: "스톡홀름", en: "Stockholm", country: "스웨덴", zone: "Europe/Stockholm" },
  { name: "오슬로", en: "Oslo", country: "노르웨이", zone: "Europe/Oslo" },
  { name: "코펜하겐", en: "Copenhagen", country: "덴마크", zone: "Europe/Copenhagen" },
  { name: "헬싱키", en: "Helsinki", country: "핀란드", zone: "Europe/Helsinki" },
  { name: "아테네", en: "Athens", country: "그리스", zone: "Europe/Athens" },
  { name: "부쿠레슈티", en: "Bucharest", country: "루마니아", zone: "Europe/Bucharest" },
  { name: "키이우", en: "Kyiv", country: "우크라이나", zone: "Europe/Kyiv" },

  // 북미
  { name: "뉴욕", en: "New York", country: "미국", zone: "America/New_York" },
  { name: "워싱턴", en: "Washington DC", country: "미국", zone: "America/New_York" },
  { name: "보스턴", en: "Boston", country: "미국", zone: "America/New_York" },
  { name: "애틀랜타", en: "Atlanta", country: "미국", zone: "America/New_York" },
  { name: "마이애미", en: "Miami", country: "미국", zone: "America/New_York" },
  { name: "디트로이트", en: "Detroit", country: "미국", zone: "America/Detroit" },
  { name: "시카고", en: "Chicago", country: "미국", zone: "America/Chicago" },
  { name: "오스틴", en: "Austin", country: "미국", zone: "America/Chicago" },
  { name: "댈러스", en: "Dallas", country: "미국", zone: "America/Chicago" },
  { name: "휴스턴", en: "Houston", country: "미국", zone: "America/Chicago" },
  { name: "덴버", en: "Denver", country: "미국", zone: "America/Denver" },
  { name: "솔트레이크시티", en: "Salt Lake City", country: "미국", zone: "America/Denver" },
  { name: "피닉스", en: "Phoenix", country: "미국", zone: "America/Phoenix" },
  { name: "시애틀", en: "Seattle", country: "미국", zone: "America/Los_Angeles" },
  { name: "포틀랜드", en: "Portland", country: "미국", zone: "America/Los_Angeles" },
  { name: "샌프란시스코", en: "San Francisco", country: "미국", zone: "America/Los_Angeles" },
  { name: "산호세", en: "San Jose", country: "미국", zone: "America/Los_Angeles" },
  { name: "로스앤젤레스", en: "Los Angeles", country: "미국", zone: "America/Los_Angeles" },
  { name: "샌디에이고", en: "San Diego", country: "미국", zone: "America/Los_Angeles" },
  { name: "라스베이거스", en: "Las Vegas", country: "미국", zone: "America/Los_Angeles" },
  { name: "호놀룰루", en: "Honolulu", country: "미국", zone: "Pacific/Honolulu" },
  { name: "앵커리지", en: "Anchorage", country: "미국", zone: "America/Anchorage" },
  { name: "토론토", en: "Toronto", country: "캐나다", zone: "America/Toronto" },
  { name: "몬트리올", en: "Montreal", country: "캐나다", zone: "America/Toronto" },
  { name: "밴쿠버", en: "Vancouver", country: "캐나다", zone: "America/Vancouver" },
  { name: "멕시코시티", en: "Mexico City", country: "멕시코", zone: "America/Mexico_City" },
  { name: "몬테레이", en: "Monterrey", country: "멕시코", zone: "America/Monterrey" },
  { name: "티후아나", en: "Tijuana", country: "멕시코", zone: "America/Tijuana" },

  // 중남미
  { name: "파나마시티", en: "Panama City", country: "파나마", zone: "America/Panama" },
  { name: "보고타", en: "Bogota", country: "콜롬비아", zone: "America/Bogota" },
  { name: "리마", en: "Lima", country: "페루", zone: "America/Lima" },
  { name: "산티아고", en: "Santiago", country: "칠레", zone: "America/Santiago" },
  { name: "상파울루", en: "Sao Paulo", country: "브라질", zone: "America/Sao_Paulo" },
  { name: "리우데자네이루", en: "Rio de Janeiro", country: "브라질", zone: "America/Sao_Paulo" },
  { name: "마나우스", en: "Manaus", country: "브라질", zone: "America/Manaus" },
  { name: "부에노스아이레스", en: "Buenos Aires", country: "아르헨티나", zone: "America/Argentina/Buenos_Aires" },

  // 오세아니아
  { name: "시드니", en: "Sydney", country: "호주", zone: "Australia/Sydney" },
  { name: "멜버른", en: "Melbourne", country: "호주", zone: "Australia/Melbourne" },
  { name: "브리즈번", en: "Brisbane", country: "호주", zone: "Australia/Brisbane" },
  { name: "퍼스", en: "Perth", country: "호주", zone: "Australia/Perth" },
  { name: "애들레이드", en: "Adelaide", country: "호주", zone: "Australia/Adelaide" },
  { name: "캔버라", en: "Canberra", country: "호주", zone: "Australia/Sydney" },
  { name: "오클랜드", en: "Auckland", country: "뉴질랜드", zone: "Pacific/Auckland" },
  { name: "웰링턴", en: "Wellington", country: "뉴질랜드", zone: "Pacific/Auckland" },

  // 기준 시각
  { name: "협정세계시(UTC)", en: "UTC", country: "세계 표준", zone: "UTC" },
];

/** 이름 → 표준 시간대. 예전에 저장해 둔 도시 이름도 그대로 찾습니다. */
export const CITY_ZONES: Record<string, string> = Object.fromEntries(
  CITIES.map((city) => [city.name, city.zone])
);

const BY_NAME = new Map(CITIES.map((city) => [city.name, city]));

export function findCity(name: string): City | undefined {
  return BY_NAME.get(name);
}

const CHOSUNG = [
  "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
  "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
];

/** "서울" → "ㅅㅇ". 초성만 쳐도 찾게 하려고 씁니다. */
function chosungOf(text: string): string {
  return Array.from(text)
    .map((letter) => {
      const index = letter.charCodeAt(0) - 0xac00;
      return index >= 0 && index < 11172 ? CHOSUNG[Math.floor(index / 588)] : letter;
    })
    .join("");
}

const SEARCH_KEYS = new Map(
  CITIES.map((city) => {
    const plain = (text: string) => text.toLowerCase().replace(/\s+/g, "");
    return [
      city.name,
      {
        name: plain(city.name),
        chosung: chosungOf(city.name),
        en: plain(city.en),
        country: plain(city.country),
        zone: plain(city.zone),
      },
    ];
  })
);

/**
 * 친 글자와 맞는 도시를 찾습니다. 도시 이름·영문 이름·나라 이름·초성 모두 됩니다.
 * 앞글자부터 맞는 도시를 먼저 보여 줍니다.
 */
export function searchCities(query: string, exclude: string[] = []): City[] {
  const needle = query.toLowerCase().replace(/\s+/g, "");
  const skip = new Set(exclude);
  const pool = CITIES.filter((city) => !skip.has(city.name));
  if (!needle) return pool;

  const scored: { city: City; score: number }[] = [];
  for (const city of pool) {
    const keys = SEARCH_KEYS.get(city.name)!;
    let score = -1;
    if (keys.name === needle || keys.en === needle) score = 0;
    else if (keys.name.startsWith(needle) || keys.en.startsWith(needle)) score = 1;
    else if (keys.chosung.startsWith(needle)) score = 2;
    // "인도" 는 인도네시아보다 인도가 먼저 나와야 합니다.
    else if (keys.country === needle) score = 3;
    else if (keys.country.startsWith(needle)) score = 4;
    else if (keys.name.includes(needle) || keys.en.includes(needle)) score = 5;
    else if (keys.country.includes(needle) || keys.zone.includes(needle)) score = 6;
    if (score >= 0) scored.push({ city, score });
  }
  return scored.sort((a, b) => a.score - b.score).map((entry) => entry.city);
}
