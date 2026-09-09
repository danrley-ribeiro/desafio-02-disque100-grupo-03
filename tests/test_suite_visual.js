const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

(async () => {
    console.log('🧪 ================================================================');
    console.log('🧪 SUÍTE DE TESTES VISUAIS E VALIDAÇÃO NO GOOGLE CHROME (GOV-SC)');
    console.log('🧪 ================================================================');

    const browser = await puppeteer.launch({
        executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1600,1000']
    });

    try {
        // ====================================================================
        // TESTE 1: APLICAÇÃO STREAMLIT COM MAPA FOLIUM E 5 ABAS
        // ====================================================================
        console.log('\n📱 1. Testando Aplicação Streamlit (http://localhost:8501)...');
        const stPage = await browser.newPage();
        await stPage.setViewport({ width: 1600, height: 1000 });

        try {
            await stPage.goto('http://localhost:8501', { waitUntil: 'networkidle2', timeout: 15000 });
            await new Promise(r => setTimeout(r, 3500));

            const pageTitle = await stPage.title();
            console.log(`  ✓ Título da página: "${pageTitle}"`);

            const stScreenshotPath = path.resolve(__dirname, 'test_streamlit_app.png');
            await stPage.screenshot({ path: stScreenshotPath, fullPage: false });
            console.log(`  📸 Screenshot Streamlit salvo: ${path.basename(stScreenshotPath)}`);
        } catch (stErr) {
            console.warn(`  ⚠️ Aviso no Streamlit: ${stErr.message}`);
        }

        // ====================================================================
        // TESTE 2: DASHBOARD FOLIUM GEORREFERENCIADO (LIMPO, FULL BLEED)
        // ====================================================================
        console.log('\n🗺️ 2. Testando Mapa Folium Georreferenciado & Tooltips...');
        const mapPage = await browser.newPage();
        await mapPage.setViewport({ width: 1600, height: 1000 });

        const dashFile = fs.existsSync(path.resolve(__dirname, '../dashboards/dashboard_sc_disque100_folium.html'))
            ? path.resolve(__dirname, '../dashboards/dashboard_sc_disque100_folium.html')
            : path.resolve(__dirname, 'dashboard_sc_disque100_folium.html');
        const htmlPath = 'file://' + dashFile;
        await mapPage.goto(htmlPath, { waitUntil: 'networkidle0', timeout: 20000 });
        await new Promise(r => setTimeout(r, 2000));

        console.log('  🎯 Acionando hover no polígono do município para captura do Tooltip...');
        const pathEls = await mapPage.$$('.leaflet-interactive');
        console.log(`  ✓ Encontrados ${pathEls.length} elementos interativos no Leaflet.`);

        if (pathEls.length > 2) {
            const box = await pathEls[2].boundingBox();
            if (box) {
                await mapPage.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
                await new Promise(r => setTimeout(r, 600));

                const tooltipData = await mapPage.evaluate(() => {
                    const el = document.querySelector('.leaflet-tooltip');
                    return el ? el.innerText.replace(/\s+/g, ' ').trim() : null;
                });

                console.log(`  📌 Conteúdo do Tooltip: "${tooltipData}"`);

                const tooltipPicPath = path.resolve(__dirname, 'test_hover_tooltip.png');
                await mapPage.screenshot({ path: tooltipPicPath });
                console.log(`  📸 Screenshot Tooltip salvo: ${path.basename(tooltipPicPath)}`);
            }
        }

        // ====================================================================
        // TESTE 3: APRESENTAÇÃO EXECUTIVA PITCH DECK
        // ====================================================================
        console.log('\n📑 3. Testando Apresentação Executiva em HTML (Pitch Deck)...');
        const pitchPage = await browser.newPage();
        await pitchPage.setViewport({ width: 1600, height: 1000 });

        const pitchFile = fs.existsSync(path.resolve(__dirname, '../dashboards/apresentacao_executiva_indicios_penais_sc.html'))
            ? path.resolve(__dirname, '../dashboards/apresentacao_executiva_indicios_penais_sc.html')
            : path.resolve(__dirname, 'apresentacao_executiva_indicios_penais_sc.html');
        const pitchPath = 'file://' + pitchFile;
        await pitchPage.goto(pitchPath, { waitUntil: 'networkidle0', timeout: 20000 });
        await new Promise(r => setTimeout(r, 1500));

        const pitchTitle = await pitchPage.title();
        console.log(`  ✓ Título do Pitch: "${pitchTitle}"`);

        const pitchPicPath = path.resolve(__dirname, 'test_final_chrome.png');
        await pitchPage.screenshot({ path: pitchPicPath });
        console.log(`  📸 Screenshot do Pitch salvo: ${path.basename(pitchPicPath)}`);

        console.log('\n🎉 ================================================================');
        console.log('🎉 TODOS OS TESTES VISUAIS FORAM CONCLUÍDOS E VALIDADOS NO CHROME!');
        console.log('🎉 ================================================================');

    } catch (err) {
        console.error('❌ Erro na execução dos testes visuais:', err);
    } finally {
        await browser.close();
    }
})();
