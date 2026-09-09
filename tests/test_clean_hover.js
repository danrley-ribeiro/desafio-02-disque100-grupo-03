const puppeteer = require('puppeteer');
const path = require('path');

const fs = require('fs');

(async () => {
    console.log('🧪 Verificando que o cursor tooltip funciona e o box superior foi removido...');
    const browser = await puppeteer.launch({
        executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 900 });

    const dashFile = fs.existsSync(path.resolve(__dirname, '../dashboards/dashboard_sc_disque100_folium.html'))
        ? path.resolve(__dirname, '../dashboards/dashboard_sc_disque100_folium.html')
        : path.resolve(__dirname, 'dashboard_sc_disque100_folium.html');
    const htmlPath = 'file://' + dashFile;
    await page.goto(htmlPath, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 1500));

    // Verifica que hover-inspector-box não existe mais
    const hasInspectorBox = await page.$('#hover-inspector-box');
    console.log('🔍 Box "Passe o mouse no mapa" presente?', hasInspectorBox !== null ? 'SIM ❌' : 'NÃO (Removido com sucesso) ✅');

    // Testa hover em município e captura o tooltip do cursor
    const pathEls = await page.$$('.leaflet-interactive');
    const box = await pathEls[1].boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await new Promise(r => setTimeout(r, 400));

    const tooltipInfo = await page.evaluate(() => {
        const el = document.querySelector('.leaflet-tooltip');
        return el ? {
            text: el.textContent.replace(/\s+/g, ' ').trim(),
            opacity: window.getComputedStyle(el).opacity,
            display: window.getComputedStyle(el).display,
            visibility: window.getComputedStyle(el).visibility
        } : null;
    });

    console.log('📌 Tooltip no cursor ativo:', tooltipInfo);

    await browser.close();
    console.log('🎉 Validação concluída com sucesso!');
})();
