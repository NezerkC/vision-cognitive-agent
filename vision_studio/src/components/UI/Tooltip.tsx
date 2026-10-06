import React, { useState } from 'react';
import { HelpCircle } from 'lucide-react';

interface TooltipProps {
  content: string;
  children?: React.ReactNode;
}

export default function Tooltip({ content, children }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <div 
      className="relative inline-flex items-center"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
    >
      {children || <HelpCircle size={13} className="text-[#a78bfa] cursor-pointer hover:text-white transition-colors ml-1" />}
      
      {isVisible && (
        <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 z-50 w-56 p-2.5 bg-[#18181b] border border-[#3c3c3c] rounded shadow-2xl text-[10px] text-[#cccccc] font-normal leading-normal pointer-events-none backdrop-blur-md animate-fade-in">
          <div className="relative">
            {content}
            <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-[#18181b]"></div>
          </div>
        </div>
      )}
    </div>
  );
}
