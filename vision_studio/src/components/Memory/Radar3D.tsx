import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useWebSocketTelemetry, MemoryNode4D } from '../../stores/useWebSocketTelemetry';

interface MemoryNodesProps {
  nodes: MemoryNode4D[];
}

function RealtimeMemoryNodes({ nodes }: MemoryNodesProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);

  const parsedNodes = useMemo(() => {
    if (nodes && nodes.length > 0) {
      return nodes.map((n) => ({
        x: n.x || (Math.random() - 0.5) * 10,
        y: n.y || (Math.random() - 0.5) * 10,
        z: n.z || (Math.random() - 0.5) * 10,
        w: n.w || 100,
        scale: Math.max(0.1, Math.min(0.6, (n.w || 100) / 150.0)),
      }));
    }
    // Fallback simulated nodes
    const temp = [];
    for (let i = 0; i < 100; i++) {
      temp.push({
        x: (Math.random() - 0.5) * 10,
        y: (Math.random() - 0.5) * 10,
        z: (Math.random() - 0.5) * 10,
        w: 80,
        scale: Math.random() * 0.4 + 0.1,
      });
    }
    return temp;
  }, [nodes]);

  useFrame((state) => {
    if (!meshRef.current) return;
    const time = state.clock.elapsedTime;

    parsedNodes.forEach((particle, i) => {
      dummy.position.set(
        particle.x + Math.sin(time * 0.5 + i) * 0.2,
        particle.y + Math.cos(time * 0.5 + i) * 0.2,
        particle.z
      );
      dummy.scale.set(particle.scale, particle.scale, particle.scale);
      dummy.updateMatrix();
      meshRef.current!.setMatrixAt(i, dummy.matrix);
    });
    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, parsedNodes.length]}>
      <sphereGeometry args={[0.2, 16, 16]} />
      <meshStandardMaterial color="#10b981" transparent opacity={0.7} />
    </instancedMesh>
  );
}

function AutoRotateCamera() {
  useFrame((state) => {
    state.camera.position.x = Math.sin(state.clock.elapsedTime * 0.1) * 15;
    state.camera.position.z = Math.cos(state.clock.elapsedTime * 0.1) * 15;
    state.camera.lookAt(0, 0, 0);
  });
  return null;
}

export default function Radar3D() {
  const memoryNodes = useWebSocketTelemetry((state) => state.memoryNodes);

  return (
    <div className="w-full h-full flex flex-col bg-black overflow-hidden relative">
      <div className="absolute top-2 left-3 z-10 text-emerald-500 text-xs uppercase tracking-widest font-semibold opacity-70 pointer-events-none flex items-center gap-2">
        <span>Radar Latente 4D (LanceDB)</span>
        <span className="text-[10px] text-gray-400">[{memoryNodes.length || 100} Nodos]</span>
      </div>

      <div className="flex-grow">
        <Canvas camera={{ position: [0, 0, 15], fov: 60 }}>
          <color attach="background" args={['#050505']} />
          <ambientLight intensity={0.5} />
          <pointLight position={[10, 10, 10]} intensity={1} color="#10b981" />
          <pointLight position={[-10, -10, -10]} intensity={0.5} color="#3b82f6" />

          <gridHelper args={[20, 20, '#111', '#222']} rotation={[Math.PI / 4, 0, 0]} />

          <RealtimeMemoryNodes nodes={memoryNodes} />

          <AutoRotateCamera />
        </Canvas>
      </div>
    </div>
  );
}
