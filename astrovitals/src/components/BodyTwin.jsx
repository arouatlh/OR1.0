import { useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { useSim } from '../store/useSim'
// Procedural holographic body. Anatomical visualization only, NOT a medical scan.
const PARTS = [
  { id: 'head', pos: [0, 1.72, 0], shape: 'sphere', size: [0.17] },
  { id: 'chest', pos: [0, 1.2, 0], shape: 'cap', size: [0.22, 0.35] },
  { id: 'abdomen', pos: [0, 0.75, 0], shape: 'cap', size: [0.19, 0.25] },
  { id: 'left-arm', pos: [-0.38, 1.15, 0], shape: 'cap', size: [0.07, 0.55] },
  { id: 'right-arm', pos: [0.38, 1.15, 0], shape: 'cap', size: [0.07, 0.55] },
  { id: 'right-hand', pos: [0.4, 0.62, 0], shape: 'sphere', size: [0.09] },
  { id: 'left-hand', pos: [-0.4, 0.62, 0], shape: 'sphere', size: [0.09] },
  { id: 'left-leg', pos: [-0.13, 0, 0], shape: 'cap', size: [0.1, 0.75] },
  { id: 'right-leg', pos: [0.13, 0, 0], shape: 'cap', size: [0.1, 0.75] },
]
export const REGION_INFO = {
  head: 'Head. No head sensors in this prototype.', chest: 'Chest / cardiovascular. Heart rate from wrist optical sensor (simulated).',
  abdomen: 'Abdomen. No sensors assigned.', 'right-hand': 'Right hand. Astronaut-reported symptoms would appear here.', 'left-hand': 'Left hand.',
  'left-arm': 'Left arm.', 'right-arm': 'Right arm.', 'left-leg': 'Left leg.', 'right-leg': 'Right leg.',
}
function Part({ p, selected, alert }) {
  const [hover, setHover] = useState(false)
  const select = useSim((s) => s.selectRegion)
  const hot = alert && p.id === 'chest'
  const color = hot ? '#FF617A' : selected ? '#62E5FF' : hover ? '#35D5FF' : '#1E7FA8'
  return (
    <mesh position={p.pos} onClick={(e) => { e.stopPropagation(); select(p.id) }} onPointerOver={(e) => { e.stopPropagation(); setHover(true) }} onPointerOut={() => setHover(false)}>
      {p.shape === 'sphere' ? <sphereGeometry args={[p.size[0], 24, 24]} /> : <capsuleGeometry args={[p.size[0], p.size[1], 6, 16]} />}
      <meshStandardMaterial color={color} transparent opacity={selected || hot ? 0.75 : 0.35} emissive={color} emissiveIntensity={0.4} />
    </mesh>
  )
}
export default function BodyTwin() {
  const region = useSim((s) => s.region)
  const alert = useSim((s) => s.alerts.some((a) => a.active))
  return (
    <div className="twin" role="img" aria-label="Interactive 3D digital twin. Drag to rotate, scroll to zoom, click a region.">
      <Canvas camera={{ position: [0, 1.1, 3.4], fov: 40 }}>
        <ambientLight intensity={0.6} /><pointLight position={[2, 3, 3]} intensity={30} color="#35D5FF" />
        <gridHelper args={[4, 20, '#35D5FF', '#10243A']} position={[0, -0.4, 0]} />
        {PARTS.map((p) => <Part key={p.id} p={p} selected={region === p.id} alert={alert} />)}
        <OrbitControls target={[0, 0.9, 0]} enablePan={false} minDistance={1.5} maxDistance={6} makeDefault />
      </Canvas>
    </div>
  )
}
