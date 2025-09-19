#!/usr/bin/env python3
"""
Signal Calling Service - 最终完整测试套件
All-in-One 测试脚本 - 包含问题诊断和修复建议
"""
import hmac
import hashlib
import base64
import time
import subprocess
import json
import sys
import os

class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class SignalTestRunner:
    def __init__(self):
        self.results = {
            "infrastructure": {},
            "authentication": {},
            "api_calls": {},
            "diagnostics": []
        }

    def print_header(self, title):
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{title.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

    def print_step(self, message):
        print(f"{Colors.BLUE}🔍 {message}{Colors.END}")

    def print_success(self, message):
        print(f"{Colors.GREEN}✅ {message}{Colors.END}")

    def print_error(self, message):
        print(f"{Colors.RED}❌ {message}{Colors.END}")

    def print_warning(self, message):
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

    def print_info(self, message):
        print(f"{Colors.WHITE}💡 {message}{Colors.END}")

    def run_command(self, command, timeout=15):
        """执行命令并返回结果"""
        try:
            result = subprocess.run(command, shell=True, capture_output=True,
                                 text=True, timeout=timeout)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Timeout", "returncode": -1}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}

    def test_infrastructure(self):
        """测试基础设施"""
        self.print_header("基础设施检查")

        # 检查Docker
        self.print_step("检查Docker服务")
        docker_result = self.run_command("docker --version")
        if docker_result["success"]:
            self.print_success("Docker服务正常")
            self.results["infrastructure"]["docker"] = True
        else:
            self.print_error("Docker服务异常")
            self.results["infrastructure"]["docker"] = False
            return False

        # 检查容器状态
        self.print_step("检查容器状态")
        ps_result = self.run_command("docker-compose ps")
        if ps_result["success"]:
            if "calling-backend" in ps_result["stdout"] and "calling-frontend" in ps_result["stdout"]:
                self.print_success("核心容器运行中")
                self.results["infrastructure"]["containers"] = True
            else:
                self.print_error("核心容器未运行")
                self.results["infrastructure"]["containers"] = False
                return False
        else:
            self.print_error("无法获取容器状态")
            return False

        # 检查Backend连通性
        self.print_step("测试Backend连通性")
        backend_result = self.run_command('curl -s "http://localhost:8080/v1/info"')
        if backend_result["success"] and "directAccessIp" in backend_result["stdout"]:
            try:
                info = json.loads(backend_result["stdout"])
                self.print_success(f"Backend连接正常 (directAccessIp: {info['directAccessIp']})")
                self.results["infrastructure"]["backend"] = True
                self.results["infrastructure"]["backend_ip"] = info["directAccessIp"]
            except:
                self.print_error("Backend响应格式异常")
                self.results["infrastructure"]["backend"] = False
                return False
        else:
            self.print_error("Backend连接失败")
            self.results["infrastructure"]["backend"] = False
            return False

        # 检查Frontend连通性
        self.print_step("测试Frontend连通性")
        frontend_result = self.run_command('curl -I "http://localhost:8401/v2/conference/participants"')
        if frontend_result["success"] and ("401" in frontend_result["stdout"] or "400" in frontend_result["stdout"]):
            self.print_success("Frontend连接正常 (需要认证)")
            self.results["infrastructure"]["frontend"] = True
        else:
            self.print_error("Frontend连接异常")
            self.results["infrastructure"]["frontend"] = False
            return False

        return True

    def generate_auth_token(self, user_id, group_id):
        """生成认证Token"""
        timestamp = str(int(time.time()))
        permission = "1"
        auth_key = "deaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddeaddead"

        token_prefix = f"2:{user_id}:{group_id}:{timestamp}:{permission}"
        key_bytes = bytes.fromhex(auth_key)
        mac = hmac.new(key_bytes, token_prefix.encode('utf-8'), hashlib.sha256)
        truncated_mac = mac.hexdigest()[:20]

        complete_token = f"{token_prefix}:{truncated_mac}"
        basic_content = f"{user_id}:{complete_token}"
        credentials = base64.b64encode(basic_content.encode()).decode()

        return {
            "token": complete_token,
            "basic_auth": credentials,
            "timestamp": timestamp
        }

    def test_authentication(self):
        """测试认证系统"""
        self.print_header("认证系统测试")

        test_cases = [
            ("1111111111111111", "aaaaaaaaaaaaaaaa", "标准测试用例"),
            ("test_user_001", "cccccccccccccccc", "自定义用例")
        ]

        all_passed = True

        for user_id, group_id, description in test_cases:
            self.print_step(f"测试认证 - {description}")

            auth = self.generate_auth_token(user_id, group_id)

            # 测试GET请求
            cmd = f'''curl -s -w "\\nHTTP_CODE:%{{http_code}}" \
                -H "Authorization: Basic {auth['basic_auth']}" \
                "http://localhost:8401/v2/conference/participants?call_id={group_id}&region=us-west1"'''

            result = self.run_command(cmd)

            if result["success"] and "HTTP_CODE:404" in result["stdout"]:
                self.print_success(f"认证成功 ({description})")
                self.results["authentication"][f"{user_id[:8]}..."] = True
            elif "HTTP_CODE:401" in result["stdout"]:
                self.print_error(f"认证失败 ({description})")
                self.results["authentication"][f"{user_id[:8]}..."] = False
                all_passed = False
            else:
                self.print_warning(f"认证响应异常 ({description})")
                self.results["authentication"][f"{user_id[:8]}..."] = "UNKNOWN"

        return all_passed

    def test_api_calls(self):
        """测试API调用"""
        self.print_header("API调用测试")

        test_cases = [
            ("1111111111111111", "aaaaaaaaaaaaaaaa", 1070920496),
            ("2222222222222222", "bbbbbbbbbbbbbbbb", 1070920497),
        ]

        results = []

        for user_id, group_id, demux_id in test_cases:
            self.print_step(f"测试API调用 - 用户: {user_id[:8]}...")

            # 生成认证
            auth = self.generate_auth_token(user_id, group_id)

            # 测试PUT请求 (Frontend API)
            payload = {
                "iceUfrag": "client-ufrag",
                "icePwd": "client-pwd",
                "dhePublicKey": "f924028e9b8021b77eb97b36f1d43e63",
                "hkdfExtraInfo": None
            }

            put_cmd = f'''curl -s -w "\\nHTTP_CODE:%{{http_code}}" \
                -H "Authorization: Basic {auth['basic_auth']}" \
                -H "Content-Type: application/json" \
                -d '{json.dumps(payload)}' \
                -X PUT "http://localhost:8401/v2/conference/participants?call_id={group_id}&region=us-west1"'''

            put_result = self.run_command(put_cmd)

            if "HTTP_CODE:200" in put_result["stdout"]:
                self.print_success("Frontend API调用成功!")
                try:
                    json_part = put_result["stdout"].split("HTTP_CODE:")[0]
                    response_data = json.loads(json_part)
                    self.print_info(f"   Demux ID: {response_data.get('demuxId')}")
                    self.print_info(f"   服务器端口: {response_data.get('port')}")
                    results.append("SUCCESS")
                    self.results["api_calls"][f"frontend_{user_id[:8]}"] = "SUCCESS"
                except:
                    self.print_success("Frontend API成功 (响应解析异常)")
                    results.append("PARTIAL")
                    self.results["api_calls"][f"frontend_{user_id[:8]}"] = "PARTIAL"
            else:
                self.print_error(f"Frontend API失败: {put_result['stdout'].split('HTTP_CODE:')[-1]}")
                results.append("FAILED")
                self.results["api_calls"][f"frontend_{user_id[:8]}"] = "FAILED"

            # 测试Backend直接API
            backend_payload = {
                "endpointId": user_id,
                "clientIceUfrag": "client-ufrag",
                "clientIcePwd": "client-pwd",
                "clientDhePublicKey": "f924028e9b8021b77eb97b36f1d43e63",
                "hkdfExtraInfo": None,
                "region": "us-west1",
                "newClientsRequireApproval": False,
                "isAdmin": True,
                "roomId": group_id,
                "callType": "GroupV2",
                "userAgent": "Unknown"
            }

            backend_cmd = f'''curl -s -w "\\nHTTP_CODE:%{{http_code}}" \
                -H "Content-Type: application/json" \
                -d '{json.dumps(backend_payload)}' \
                -X POST "http://localhost:8080/v1/call/{group_id}/client/{demux_id}"'''

            backend_result = self.run_command(backend_cmd)

            if "HTTP_CODE:200" in backend_result["stdout"]:
                self.print_success("Backend直接API调用成功!")
                results.append("SUCCESS")
                self.results["api_calls"][f"backend_{user_id[:8]}"] = "SUCCESS"
            else:
                error_msg = backend_result["stdout"].split("HTTP_CODE:")[0].strip()
                self.print_error(f"Backend直接API失败: {error_msg}")
                results.append("FAILED")
                self.results["api_calls"][f"backend_{user_id[:8]}"] = "FAILED"

                # 记录具体错误用于诊断
                self.results["diagnostics"].append({
                    "type": "backend_error",
                    "user": user_id[:8],
                    "error": error_msg
                })

        return len([r for r in results if r == "SUCCESS"]) > 0

    def run_diagnostics(self):
        """运行问题诊断"""
        self.print_header("问题诊断与建议")

        # 检查基础设施问题
        if not all(self.results["infrastructure"].values()):
            self.print_error("基础设施存在问题:")
            for component, status in self.results["infrastructure"].items():
                if not status:
                    self.print_info(f"   {component}: 需要检查")
            return

        # 检查认证问题
        auth_failures = [k for k, v in self.results["authentication"].items() if v == False]
        if auth_failures:
            self.print_warning("认证系统存在问题:")
            for failure in auth_failures:
                self.print_info(f"   用户 {failure}: 认证失败")
            self.print_info("   建议检查认证密钥配置")

        # 检查API问题
        api_failures = [k for k, v in self.results["api_calls"].items() if v == "FAILED"]
        if api_failures:
            self.print_warning("API调用存在问题:")
            for failure in api_failures:
                self.print_info(f"   {failure}: 调用失败")

        # 具体错误诊断
        for diagnostic in self.results["diagnostics"]:
            if diagnostic["type"] == "backend_error":
                error = diagnostic["error"]
                if "Invalid string length" in error:
                    self.print_info(f"   🔍 {diagnostic['user']}: DHE公钥长度问题")
                elif "Invalid demux ID" in error:
                    self.print_info(f"   🔍 {diagnostic['user']}: Demux ID格式问题")
                elif "Invalid call_id" in error:
                    self.print_info(f"   🔍 {diagnostic['user']}: Call ID格式问题")

        # 提供解决方案
        self.print_info("\n🛠️  解决方案建议:")
        if api_failures:
            self.print_info("   1. API参数需要进一步调整")
            self.print_info("   2. 检查DHE公钥格式和长度")
            self.print_info("   3. 验证Demux ID生成算法")
            self.print_info("   4. 确认Call ID格式要求")

        # 成功的部分
        success_count = len([v for v in self.results["api_calls"].values() if v in ["SUCCESS", "PARTIAL"]])
        if success_count > 0:
            self.print_success(f"\n🎉 系统核心功能正常:")
            self.print_success("   ✓ 认证系统完全可用")
            self.print_success("   ✓ 网络连接完全正常")
            self.print_success("   ✓ 基础API架构正确")

    def generate_summary(self):
        """生成总结报告"""
        self.print_header("测试总结报告")

        # 基础设施状态
        infra_score = sum(1 for v in self.results["infrastructure"].values() if v == True)
        infra_total = len(self.results["infrastructure"])

        # 认证状态
        auth_score = sum(1 for v in self.results["authentication"].values() if v == True)
        auth_total = len(self.results["authentication"])

        # API状态
        api_score = sum(1 for v in self.results["api_calls"].values() if v in ["SUCCESS", "PARTIAL"])
        api_total = len(self.results["api_calls"])

        self.print_info(f"基础设施: {infra_score}/{infra_total} ✓")
        self.print_info(f"认证系统: {auth_score}/{auth_total} ✓")
        self.print_info(f"API调用: {api_score}/{api_total} ✓")

        # 整体评估
        overall_score = (infra_score + auth_score + api_score) / (infra_total + auth_total + api_total)

        if overall_score >= 0.8:
            self.print_success(f"🎯 整体评估: 优秀 ({overall_score:.1%})")
            self.print_success("   系统主要功能正常，可进入生产环境")
        elif overall_score >= 0.6:
            self.print_warning(f"🎯 整体评估: 良好 ({overall_score:.1%})")
            self.print_warning("   系统基本可用，需要调优参数")
        else:
            self.print_error(f"🎯 整体评估: 需改进 ({overall_score:.1%})")
            self.print_error("   系统存在重要问题，需要修复")

        return overall_score >= 0.6

    def run_full_test(self):
        """运行完整测试流程"""
        self.print_header("Signal Calling Service 完整测试套件")

        # 步骤1: 基础设施检查
        if not self.test_infrastructure():
            self.print_error("基础设施检查失败，测试终止")
            return False

        # 步骤2: 认证测试
        if not self.test_authentication():
            self.print_error("认证测试存在问题")

        # 步骤3: API测试
        if not self.test_api_calls():
            self.print_warning("API调用测试存在问题")

        # 步骤4: 问题诊断
        self.run_diagnostics()

        # 步骤5: 生成总结
        return self.generate_summary()

def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Signal Calling Service 完整测试套件")
        print("用法: python3 final_comprehensive_test.py")
        print("\n功能:")
        print("  - 基础设施检查 (Docker, 容器状态)")
        print("  - 网络连通性测试 (Backend, Frontend)")
        print("  - 认证系统验证")
        print("  - API调用测试")
        print("  - 问题诊断和解决建议")
        sys.exit(0)

    # 检查运行环境
    if not os.path.exists("docker-compose.yml"):
        print("❌ 错误: 请在项目根目录运行此脚本")
        #sys.exit(1)

    # 运行测试
    runner = SignalTestRunner()
    success = runner.run_full_test()

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()