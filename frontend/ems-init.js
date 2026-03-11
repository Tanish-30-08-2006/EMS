// ems-init.js — loaded on every EMS page after config.js
// Restores accent colour and compact mode from localStorage (persists across pages/sessions)

(function() {
  const ACCENT_MAP = {
    '#2952cc': { hover: '#3b6aee', subtle: 'rgba(41,82,204,0.10)',  text: '#a8bfff'  },
    '#0f766e': { hover: '#115e59', subtle: 'rgba(15,118,110,0.10)', text: '#5eead4'  },
    '#7c3aed': { hover: '#8b5cf6', subtle: 'rgba(124,58,237,0.10)', text: '#c4b5fd'  },
    '#b45309': { hover: '#92400e', subtle: 'rgba(180,83,9,0.10)',   text: '#fcd34d'  },
    '#be123c': { hover: '#9f1239', subtle: 'rgba(190,18,60,0.10)',  text: '#fda4af'  },
    '#374151': { hover: '#1f2937', subtle: 'rgba(55,65,81,0.10)',   text: '#9ca3af'  },
  };

  // Use localStorage so colour persists across ALL pages and sessions
  const savedAccent = localStorage.getItem('ems_accent');
  if (savedAccent && ACCENT_MAP[savedAccent]) {
    const root = document.documentElement;
    const data = ACCENT_MAP[savedAccent];
    root.style.setProperty('--accent',        savedAccent);
    root.style.setProperty('--accent-hover',  data.hover);
    root.style.setProperty('--accent-subtle', data.subtle);
    root.style.setProperty('--accent-text',   data.text);
  }

  // Restore compact mode
  if (localStorage.getItem('ems_compact') === '1') {
    document.documentElement.classList.add('compact');
  }
})();