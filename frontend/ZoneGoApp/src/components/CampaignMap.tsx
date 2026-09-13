import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import { useEffect } from 'react'
import L from 'leaflet'
import { formatUsd, formatDistance, type SearchHit } from '../lib/api'

/**
 * Leaflet's default marker icons reference image files by a relative path
 * that Vite's bundler doesn't resolve correctly out of the box — a known,
 * common breakage. Custom divIcon markers sidestep the problem entirely:
 * no image assets to load, and they match the app's own brand colors
 * instead of Leaflet's default blue pin.
 */
function createPin(color: string): L.DivIcon {
  return L.divIcon({
    className: '',
    html: `<div style="width:16px;height:16px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.4);"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  })
}

const VISITOR_PIN = createPin('#16a38a')
const CAMPAIGN_PIN = createPin('#16a38a')
const BOOSTED_PIN = createPin('#f0a030')

export function openDirections(lat: number, lon: number) {
  window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`, '_blank')
}

/**
 * Recenters an already-mounted map when the visitor's own coordinates
 * change (switching between the Delancey demo location and real GPS)
 * without remounting the whole map and losing zoom/pan state.
 */
function Recenter({ lat, lon }: { lat: number; lon: number }) {
  const map = useMap()
  useEffect(() => {
    map.setView([lat, lon], map.getZoom())
  }, [lat, lon, map])
  return null
}

interface CampaignMapProps {
  center: { lat: number; lon: number }
  hits: SearchHit[]
  onSelectCampaign: (hit: SearchHit) => void
}

export function CampaignMap({ center, hits, onSelectCampaign }: CampaignMapProps) {
  return (
    <div className="relative mt-4 h-64 w-full overflow-hidden rounded-2xl border border-border">
      <MapContainer
        center={[center.lat, center.lon]}
        zoom={15}
        scrollWheelZoom
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Recenter lat={center.lat} lon={center.lon} />

        <Marker position={[center.lat, center.lon]} icon={VISITOR_PIN}>
          <Popup>You are here</Popup>
        </Marker>

        {hits.map((hit) => {
          const isBoosted = hit.campaign.pays_double_today
          return (
            <Marker
              key={hit.campaign.campaign_id}
              position={[hit.campaign.lat, hit.campaign.lon]}
              icon={isBoosted ? BOOSTED_PIN : CAMPAIGN_PIN}
            >
              <Popup>
                <div style={{ minWidth: 160 }}>
                  <p style={{ fontWeight: 600, margin: 0 }}>{hit.campaign.merchant_name}</p>
                  <p style={{ margin: '2px 0', color: '#6b7280', fontSize: 12 }}>
                    {formatDistance(hit.distance_meters)} · {formatUsd(hit.campaign.reward_today)}
                  </p>
                  <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                    <button
                      type="button"
                      onClick={() => onSelectCampaign(hit)}
                      style={{
                        flex: 1,
                        background: '#16a38a',
                        color: 'white',
                        border: 'none',
                        borderRadius: 8,
                        padding: '4px 8px',
                        fontSize: 12,
                        cursor: 'pointer',
                      }}
                    >
                      Select
                    </button>
                    <button
                      type="button"
                      onClick={() => openDirections(hit.campaign.lat, hit.campaign.lon)}
                      style={{
                        flex: 1,
                        background: 'white',
                        color: '#16231f',
                        border: '1px solid #e7e5dd',
                        borderRadius: 8,
                        padding: '4px 8px',
                        fontSize: 12,
                        cursor: 'pointer',
                      }}
                    >
                      Directions
                    </button>
                  </div>
                </div>
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>
    </div>
  )
}