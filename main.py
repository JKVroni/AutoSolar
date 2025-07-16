# -*- coding: utf-8 -*-

import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon
import re

CENTER = [36.783316, 126.452611]
WFS_URL = "https://api.vworld.kr/ned/wfs/getCtnlgsSpceWFS"
API_KEY = "2999371B-F71D-32DA-85C3-ED9AB3C48403"

color_map = {
    "농지": "#f4a261",     # 주황색
    "염전": "#2a9d8f",     # 청록색
    "양어장": "#e76f51",   # 빨강색
    "임야": "#264653"      # 진회색
}

st.sidebar.title("지목 필터")
show_farmland = st.sidebar.checkbox("🟧 농지", value=True)
show_salt = st.sidebar.checkbox("🟩 염전", value=True)
show_fishfarm = st.sidebar.checkbox("🟥 양어장", value=True)
show_forest = st.sidebar.checkbox("⬛ 임야", value=True)

m = folium.Map(location=CENTER, zoom_start=16, control_scale=True)
st.title("Auto Solar")
st_map = st_folium(m, width=1100, height=800, returned_objects=["bounds"])

def get_bbox_from_bounds(bounds):
    if not bounds:
        return "126.450,36.782,126.455,36.785,EPSG:4326"  # fallback bbox
    south, west = bounds['_southWest']['lat'], bounds['_southWest']['lng']
    north, east = bounds['_northEast']['lat'], bounds['_northEast']['lng']
    return f"{west},{south},{east},{north},EPSG:4326"

bbox = get_bbox_from_bounds(st_map.get("bounds"))

# ✅ 진단 코드 1: bbox 확인
st.text("📦 현재 요청된 BBOX 좌표:")
st.code(bbox)

params = {
    "key": API_KEY,
    "domain": "localhost",
    "typename": "dt_d002",
    "bbox": bbox,
    "maxFeatures": 100,
    "resultType": "results",
    "srsName": "EPSG:4326",
    "output": "text/xml; subtype=gml/2.1.2",
}

response = requests.get(WFS_URL, params=params, verify=False)

# ✅ 진단 코드 2: 호출된 전체 URL, 응답 상태 코드
st.text("🌐 호출된 WFS API URL:")
st.code(response.url)
st.text("📥 응답 상태 코드:")
st.code(response.status_code)

tree = ET.fromstring(response.content)

if response.status_code != 200:
    st.error(f"API 요청 실패: status code {response.status_code}")
    st.stop()

if b"<gml:featureMember" not in response.content:
    st.warning("필지 데이터를 찾을 수 없습니다. 범위 안에 아무 필지도 없거나 API 파라미터가 잘못되었을 수 있습니다.")
    st.text("응답 일부:")
    st.code(response.content.decode("utf-8")[:1000])
    st.stop()


ns = {
    'gml': 'http://www.opengis.net/gml',
    'sop': 'https://www.vworld.kr'
}

features = []

for member in tree.findall(".//gml:featureMember", ns):
    g = member.find(".//gml:coordinates", ns)
    pnu = member.find(".//sop:pnu", ns).text
    symbol_tag = member.find(".//sop:lnm_lndcgr_smbol", ns)
    if symbol_tag is None or g is None:
        continue
    symbol = symbol_tag.text.strip()
    code = symbol[-1]  # 마지막 글자

     # ✅ 진단 코드 3: pnu, 지목, 좌표 데이터 출력
    st.text("🧾 필지 정보:")
    st.code(f"{pnu} - {symbol} ({code})")

    st.text("📐 좌표 데이터:")
    st.code(g.text.strip()[:300])

    coords = [(float(x), float(y)) for x, y in [pt.split(',') for pt in g.text.strip().split()]]
    polygon = Polygon(coords)

    features.append({
        "pnu": pnu,
        "code": code,
        "polygon": polygon
    })

def polygon_to_geojson(polygon, pnu):
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[list(coord) for coord in polygon.exterior.coords]]
        },
        "properties": {
            "pnu": pnu
        }
    }

m = folium.Map(location=CENTER, zoom_start=16, control_scale=True)

for feature in features:
    pnu = feature["pnu"]
    code = feature["code"]
    polygon = feature["polygon"]

    if code in ('전', '답', '과') and show_farmland:
        fill = color_map["농지"]
    elif code == '염' and show_salt:
        fill = color_map["염전"]
    elif code == '양' and show_fishfarm:
        fill = color_map["양어장"]
    elif code == '임' and show_forest:
        fill = color_map["임야"]
    else:
        fill = None

    gj = polygon_to_geojson(polygon, pnu)
    folium.GeoJson(
        gj,
        style_function=lambda x, fill=fill: {
            'fillColor': fill if fill else 'transparent',
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.3 if fill else 0.0
        },
        tooltip=folium.Tooltip(pnu)
    ).add_to(m)

st_folium(m, width=1100, height=800)
