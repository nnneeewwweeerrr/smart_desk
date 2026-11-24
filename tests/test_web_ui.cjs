const assert = require('assert').strict;
const fs = require('fs');
const vm = require('vm');

(async () => {
    const ids = ['message', 'calibrationStatus', 'cameraFeed', 'lightBadge',
        'buzzerBadge', 'statStudyMinutes', 'smoothingStatus'];
    const elements = Object.fromEntries(ids.map(id => [id, {
        textContent: '', style: {}, classList: {add() {}, remove() {}, toggle() {}}
    }]));
    const state = {
        camera_online: true, posture: 'WAIT CALIBRATION', study_status: 'idle',
        remaining_seconds: 1500, total_study_seconds: 30,
        device_mode: 'mock', light: false, buzzer_enabled: true,
        posture_smoothing: {method: 'one_euro'},
        posture_command_id: 0, calibration_result: 'waiting',
        calibration_message: '请坐正', calibration_samples: 0, calibration_required: 10
    };
    const context = vm.createContext({
        document: {getElementById: id => elements[id] || null, querySelectorAll: () => []},
        console, Date, setInterval() {}, setTimeout,
        fetch: async url => {
            let data = {};
            if (url === '/api/status') data = {...state};
            if (url === '/api/posture/calibrate') {
                state.posture_command_id += 1;
                state.calibration_result = 'failed';
                state.calibration_message = '校准失败：样本不足';
                data = {success: true, command_id: state.posture_command_id};
            }
            return {ok: true, json: async () => data};
        }
    });
    vm.runInContext(fs.readFileSync('web/js/app.js', 'utf8'), context);
    await new Promise(setImmediate);
    assert.equal(context.formatStudyDuration(30), '0分30秒');
    await context.postureControl('calibrate');
    assert.equal(elements.message.textContent, '校准失败：样本不足');
    assert.match(elements.calibrationStatus.textContent, /样本不足/);
    assert.match(elements.lightBadge.textContent, /模拟/);
    assert.match(elements.buzzerBadge.textContent, /模拟/);
    state.device_mode = 'mixed';
    state.buzzer_mode = 'gpio';
    state.light_mode = 'mock';
    state.buzzer_enabled = false;
    await context.refreshStatus();
    assert.match(elements.lightBadge.textContent, /模拟/);
    assert.equal(elements.buzzerBadge.textContent, '已静音（实体）');
    assert.match(elements.smoothingStatus.textContent, /1€ Filter/);
    state.camera_online = false;
    await context.refreshStatus();
    assert.equal(elements.cameraFeed.style.visibility, 'hidden');
    state.camera_online = true;
    await context.refreshStatus();
    assert.equal(elements.cameraFeed.style.visibility, 'visible');
    console.log('WEB_UI_OK: execution receipt, seconds, mock labels, offline/recovery');
})().catch(error => {console.error(error); process.exitCode = 1;});
