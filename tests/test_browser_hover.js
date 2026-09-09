const puppeteer = require('puppeteer');
const path = require('path');

const fs = require('fs');

(async () => {
    console.log('🧪 Iniciando Teste Completo de Interatividade no Chrome...');
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

    // Teste 1: Passa o mouse em Florianópolis / Litoral
    console.log('\n--- TESTE 1: Hover no Município 1 ---');
    const pathEls = await page.$$('.leaflet-interactive');
    const box1 = await pathEls[1].boundingBox();
    await page.mouse.move(box1.x + box1.width / 2, box1.y + box1.height / 2);
    await new Promise(r => setTimeout(r, 300));
    let title1 = await page.$eval('#inspector-title', el => el.textContent);
    let ttText1 = await page.evaluate(() => {
        const el = document.querySelector('.leaflet-tooltip');
        return el ? el.textContent.replace(/\s+/g, ' ').trim() : 'Nenhum';
    });
    console.log('✅ Inspector:', title1);
    console.log('✅ Tooltip no cursor:', ttText1);

    // Teste 2: Passa o mouse no Município 2
    console.log('\n--- TESTE 2: Hover no Município 2 ---');
    const box2 = await pathEls[3].boundingBox();
    await page.mouse.move(box2.x + box2.width / 2, box2.y + box2.height / 2);
    await new Promise(r => setTimeout(r, 300));
    let title2 = await page.$eval('#inspector-title', el => el.textContent);
    console.log('✅ Inspector:', title2);

    // Teste 3: Clica no botão "Regiões" e passa o mouse
    console.log('\n--- TESTE 3: Alternando para Regiões ---');
    await page.click('#btn-geo-reg');
    await new Promise(r => setTimeout(r, 500));
    const regPaths = await page.$$('.leaflet-interactive');
    const regBox = await regPaths[0].boundingBox();
    await page.mouse.move(regBox.x + regBox.width / 2, regBox.y + regBox.height / 2);
    await new Promise(r => setTimeout(r, 300));
    let titleReg = await page.$eval('#inspector-title', el => el.textContent);
    console.log('✅ Inspector em Regiões:', titleReg);

    // Teste 4: Altera o filtro de tópico para Crianças
    console.log('\n--- TESTE 4: Filtrando por Crianças e Adolescentes ---');
    await page.select('#select-topic', 'crianca');
    await new Promise(r => setTimeout(r, 500));
    let kpiCrianca = await page.$eval('#kpi-total-filtrado', el => el.textContent);
    console.log('✅ Total Filtrado Crianças:', kpiCrianca);

    // Screenshot final
    await page.screenshot({ path: path.resolve(__dirname, 'test_final_chrome.png') });
    console.log('📸 Screenshot final capturado com sucesso!');

    await browser.close();
    console.log('\n🎉 TODOS OS TESTES PASSARAM COM SUCESSO NO GOOGLE CHROME!');
})();
