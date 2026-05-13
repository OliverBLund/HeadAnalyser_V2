// Try to import the noise function, with fallback
let noise;

try {
    // Try to import from local module
    const module = await import("./perlin-noise.js");
    noise = module.noise;
} catch (error) {
    console.warn('Failed to import perlin-noise module:', error);
    // Fallback: Create a simple noise function
    noise = function(x, y, z = 0) {
        // Simple pseudo-random noise function as fallback
        const seed = x * 12.9898 + y * 78.233 + z * 37.719;
        return (Math.sin(seed) * 43758.5453123) % 1;
    };
}

function initGISAnimation() {
    const canvas = document.getElementById('gis-canvas');
    if (!canvas) {
        console.error('GIS canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        console.error('Canvas context not available');
        return;
    }

    console.log('GIS Animation starting...');

    // Editable values
    const thresholdIncrement = 4;
    const thickLineThresholdMultiple = 3;
    const res = 4.5;
    const baseZOffset = 0.000055;
    const lineColor = '#EDEDED80';

    let currentThreshold = 0;
    let cols = 0;
    let rows = 0;
    let zOffset = 0;
    let zBoostValues = [];
    let noiseMin = 100;
    let noiseMax = 0;
    let inputValues = [];

    function resizeCanvas() {
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
        cols = Math.floor(canvas.width / res) + 1;
        rows = Math.floor(canvas.height / res) + 1;

        console.log(`Canvas resized to ${canvas.width}x${canvas.height}, grid: ${cols}x${rows}`);

        // Initialize zBoostValues
        zBoostValues = [];
        for (let y = 0; y < rows; y++) {
            zBoostValues[y] = [];
            for (let x = 0; x <= cols; x++) {
                zBoostValues[y][x] = 0;
            }
        }
    }

    function generateNoise() {
        inputValues = [];
        for (let y = 0; y < rows; y++) {
            inputValues[y] = [];
            for (let x = 0; x <= cols; x++) {
                try {
                    inputValues[y][x] = noise(x * 0.02, y * 0.02, zOffset + (zBoostValues[y]?.[x] || 0)) * 100;
                    if (inputValues[y][x] < noiseMin) noiseMin = inputValues[y][x];
                    if (inputValues[y][x] > noiseMax) noiseMax = inputValues[y][x];
                    if (zBoostValues[y]?.[x] > 0) {
                        zBoostValues[y][x] *= 0.99;
                    }
                } catch (error) {
                    console.error('Error generating noise:', error);
                    inputValues[y][x] = 0;
                }
            }
        }
    }

    function renderAtThreshold() {
        ctx.beginPath();
        ctx.strokeStyle = lineColor;
        ctx.lineWidth = currentThreshold % (thresholdIncrement * thickLineThresholdMultiple) === 0 ? 2 : 1;

        for (let y = 0; y < inputValues.length - 1; y++) {
            for (let x = 0; x < inputValues[y].length - 1; x++) {
                if (inputValues[y][x] > currentThreshold && inputValues[y][x + 1] > currentThreshold && inputValues[y + 1][x + 1] > currentThreshold && inputValues[y + 1][x] > currentThreshold) continue;
                if (inputValues[y][x] < currentThreshold && inputValues[y][x + 1] < currentThreshold && inputValues[y + 1][x + 1] < currentThreshold && inputValues[y + 1][x] < currentThreshold) continue;
                
                let gridValue = binaryToType(
                    inputValues[y][x] > currentThreshold ? 1 : 0,
                    inputValues[y][x + 1] > currentThreshold ? 1 : 0,
                    inputValues[y + 1][x + 1] > currentThreshold ? 1 : 0,
                    inputValues[y + 1][x] > currentThreshold ? 1 : 0
                );

                placeLines(gridValue, x, y);
            }
        }
        ctx.stroke();
    }

    function placeLines(gridValue, x, y) {
        let nw = inputValues[y][x];
        let ne = inputValues[y][x + 1];
        let se = inputValues[y + 1][x + 1];
        let sw = inputValues[y + 1][x];
      
        switch (gridValue) {
          case 1:
          case 14:
            const c1 = [
              x * res + res * linInterpolate(sw, se),
              y * res + res
            ];
            const d1 = [x * res, y * res + res * linInterpolate(nw, sw)];
            line(d1, c1);
            break;
          case 2:
          case 13:
            const b2 = [
              x * res + res,
              y * res + res * linInterpolate(ne, se)
            ];
            const c2 = [
              x * res + res * linInterpolate(sw, se),
              y * res + res
            ];
            line(b2, c2);
            break;
          case 3:
          case 12:
            const b3 = [
              x * res + res,
              y * res + res * linInterpolate(ne, se)
            ];
            const d3 = [x * res, y * res + res * linInterpolate(nw, sw)];
            line(d3, b3);
            break;
          case 11:
          case 4:
            const a4 = [x * res + res * linInterpolate(nw, ne), y * res];
            const b4 = [
              x * res + res,
              y * res + res * linInterpolate(ne, se)
            ];
            line(a4, b4);
            break;
          case 5:
            const a5 = [x * res + res * linInterpolate(nw, ne), y * res];
            const b5 = [
              x * res + res,
              y * res + res * linInterpolate(ne, se)
            ];
            const c5 = [
              x * res + res * linInterpolate(sw, se),
              y * res + res
            ];
            const d5 = [x * res, y * res + res * linInterpolate(nw, sw)];
            line(d5, a5);
            line(c5, b5);
            break;
          case 6:
          case 9:
            const a6 = [x * res + res * linInterpolate(nw, ne), y * res];
            const c6 = [
              x * res + res * linInterpolate(sw, se),
              y * res + res
            ];
            line(c6, a6);
            break;
          case 7:
          case 8:
            const a7 = [x * res + res * linInterpolate(nw, ne), y * res];
            const d7 = [x * res, y * res + res * linInterpolate(nw, sw)];
            line(d7, a7);
            break;
          case 10:
            const a10 = [x * res + res * linInterpolate(nw, ne), y * res];
            const b10 = [
              x * res + res,
              y * res + res * linInterpolate(ne, se)
            ];
            const c10 = [
              x * res + res * linInterpolate(sw, se),
              y * res + res
            ];
            const d10 = [x * res, y * res + res * linInterpolate(nw, sw)];
            line(a10, b10);
            line(c10, d10);
            break;
          default:
            break;
        }
    }

    function line(from, to) {
        ctx.moveTo(from[0], from[1]);
        ctx.lineTo(to[0], to[1]);
    }

    function linInterpolate(x0, x1, y0 = 0, y1 = 1) {
        if (x0 === x1) {
            return 0;
        }
        return y0 + ((y1 - y0) * (currentThreshold - x0)) / (x1 - x0);
    }

    function binaryToType(nw, ne, se, sw) {
        let a = [nw, ne, se, sw];
        return a.reduce((res, x) => (res << 1) | x);
    }

    function animate() {
        try {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            zOffset += baseZOffset;
            generateNoise();
            
            const roundedNoiseMin = Math.floor(noiseMin / thresholdIncrement) * thresholdIncrement;
            const roundedNoiseMax = Math.ceil(noiseMax / thresholdIncrement) * thresholdIncrement;
            
            for (let threshold = roundedNoiseMin; threshold < roundedNoiseMax; threshold += thresholdIncrement) {
                currentThreshold = threshold;
                renderAtThreshold();
            }
            
            noiseMin = 100;
            noiseMax = 0;

            requestAnimationFrame(animate);
        } catch (error) {
            console.error('Animation error:', error);
        }
    }

    // Initialize
    resizeCanvas();
    
    // Start animation after a short delay to ensure everything is loaded
    setTimeout(() => {
        console.log('Starting GIS animation...');
        animate();
    }, 100);

    // Handle window resize
    window.addEventListener('resize', () => {
        resizeCanvas();
    });
    
    console.log('GIS Animation initialized successfully');
}

// Initialize when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGISAnimation);
} else {
    initGISAnimation();
}