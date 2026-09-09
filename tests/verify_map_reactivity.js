const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

(async () => {
    console.log('🚀 Launching Chrome to verify map reactivity and tooltip positioning...');
    const browser = await puppeteer.launch({
        executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        headless: 'new',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-crash-reporter',
            '--disable-features=CrashReporting',
            '--user-data-dir=/Users/danrleyribeiro/Downloads/group-03-files/.chrome_profile'
        ]
    });

    try {
        const page = await browser.newPage();
        await page.setViewport({ width: 1440, height: 960 });

        console.log('🌐 Navigating to http://localhost:8501 ...');
        await page.goto('http://localhost:8501', { waitUntil: 'networkidle2', timeout: 35000 });

        // Wait for Streamlit to be ready
        await page.waitForSelector('.stApp', { timeout: 20000 });
        console.log('✅ Streamlit app loaded');

        // Wait for iframe element to appear
        await page.waitForSelector('iframe', { timeout: 20000 });
        console.log('✅ Found iframe element on page');

        await new Promise(r => setTimeout(r, 4000));

        // Get iframe element handle
        const iframes = await page.$$('iframe');
        console.log(`Found ${iframes.length} iframes on page`);

        let frame = null;
        for (const ifr of iframes) {
            const f = await ifr.contentFrame();
            if (f) {
                const hasLegend = await f.$('#legend-title');
                if (hasLegend) {
                    frame = f;
                    console.log('✅ Found Folium map frame with #legend-title!');
                    break;
                }
            }
        }

        if (!frame && iframes.length > 0) {
            frame = await iframes[0].contentFrame();
        }

        if (!frame) {
            console.error('❌ Could not get content frame from iframe');
            await browser.close();
            return;
        }

        // Check legend title inside iframe
        let legendText = await frame.$eval('#legend-title', el => el.innerText).catch(e => 'not found');
        console.log(`📌 Initial Map Legend Title: "${legendText}"`);

        // Check number of peak markers
        let peakCount = await frame.$$eval('.peak-marker-wrapper', els => els.length);
        console.log(`🎯 Initial Peak Markers Count: ${peakCount}`);

        // Take initial screenshot
        await page.screenshot({ path: '/Users/danrleyribeiro/Downloads/group-03-files/test_map_initial.png', fullPage: false });
        console.log('📸 Saved test_map_initial.png');

        // Hover over the first peak marker to trigger tooltip
        const marker = await frame.$('.peak-marker-wrapper');
        if (marker) {
            const markerBox = await marker.boundingBox();
            console.log(`📍 Marker #1 Bounding Box: x=${markerBox.x.toFixed(1)}, y=${markerBox.y.toFixed(1)}, w=${markerBox.width}, h=${markerBox.height}`);
            
            // Move mouse to marker center
            await page.mouse.move(markerBox.x + markerBox.width / 2, markerBox.y + markerBox.height / 2);
            await new Promise(r => setTimeout(r, 800));

            // Check tooltip
            const tooltip = await frame.$('.leaflet-tooltip.custom-sc-tooltip');
            if (tooltip) {
                const tooltipBox = await tooltip.boundingBox();
                const tooltipText = await frame.evaluate(el => el.innerText, tooltip);
                const tooltipZIndex = await frame.evaluate(el => window.getComputedStyle(el.closest('.leaflet-pane') || el).zIndex, tooltip);
                console.log(`💬 Tooltip Visible! Text preview: "${tooltipText.replace(/\n/g, ' | ')}"`);
                if (tooltipBox) {
                    console.log(`💬 Tooltip Box: x=${tooltipBox.x.toFixed(1)}, y=${tooltipBox.y.toFixed(1)}, w=${tooltipBox.width}, h=${tooltipBox.height}`);
                    console.log(`💬 Tooltip Pane z-index: ${tooltipZIndex}`);
                    console.log(`📏 Tooltip Y (${tooltipBox.y.toFixed(1)}) vs Marker Y (${markerBox.y.toFixed(1)}): ${tooltipBox.y < markerBox.y ? 'Tooltip is strictly ABOVE marker (NO OVERLAP) ✅' : 'Tooltip overlaps'}`);
                }
            } else {
                console.log('⚠️ Tooltip not found after hover');
            }

            await page.screenshot({ path: '/Users/danrleyribeiro/Downloads/group-03-files/test_map_hover_marker.png' });
            console.log('📸 Saved test_map_hover_marker.png');
        }

        // Now test reactivity: execute window.applyActiveFilters directly or via sidebar
        console.log('🔄 Testing direct filter application in iframe via window.applyActiveFilters...');
        const updatedConfig = await frame.evaluate(() => {
            if (typeof window.applyActiveFilters === 'function') {
                window.applyActiveFilters({
                    topic: 'crianca',
                    metricType: 'penal',
                    scale: 50000,
                    region: 'all'
                });
                return {
                    success: true,
                    legend: document.getElementById('legend-title')?.innerText,
                    peaks: document.querySelectorAll('.peak-marker-wrapper').length
                };
            }
            return { success: false };
        });
        console.log('Result of applyActiveFilters({topic: "crianca", metricType: "penal", scale: 50000}):', updatedConfig);

        await new Promise(r => setTimeout(r, 1000));

        // Check updated marker #1 after filter
        const updatedMarker = await frame.$('.peak-marker-wrapper');
        if (updatedMarker) {
            const umb = await updatedMarker.boundingBox();
            await page.mouse.move(umb.x + umb.width / 2, umb.y + umb.height / 2);
            await new Promise(r => setTimeout(r, 800));

            const updatedTooltip = await frame.$('.leaflet-tooltip.custom-sc-tooltip');
            if (updatedTooltip) {
                const updatedTooltipText = await frame.evaluate(el => el.innerText, updatedTooltip);
                console.log(`💬 Filtered Tooltip Text: "${updatedTooltipText.replace(/\n/g, ' | ')}"`);
            }
        }

        await page.screenshot({ path: '/Users/danrleyribeiro/Downloads/group-03-files/test_map_updated_filter.png' });
        console.log('📸 Saved test_map_updated_filter.png');

    } catch (err) {
        console.error('Error during test execution:', err);
    } finally {
        await browser.close();
        console.log('🎉 Browser test completed!');
    }
})();

