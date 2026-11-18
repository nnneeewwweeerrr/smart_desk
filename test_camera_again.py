
import cv2
import numpy as np

from perception.camera import Camera


def main():
    print("1. 正在创建摄像头对象...")

    camera = Camera(camera_id=0)

    try:
        print("2. 正在启动摄像头...")
        camera.start()

        print("3. 摄像头启动完成，准备进入循环...")

        while True:
            # 读取摄像头
            result = camera.read()

            # 兼容两种返回格式：
            # 格式一：直接返回 frame
            # 格式二：返回 (ret, frame)
            if isinstance(result, tuple):
                if len(result) == 2:
                    ret, frame = result

                    if not ret:
                        continue
                else:
                    print("摄像头返回了无法识别的数据：", result)
                    continue
            else:
                frame = result

            # 检查图像是否有效
            if frame is None:
                continue

            if not isinstance(frame, np.ndarray):
                print("读取到的不是图像，实际类型：", type(frame))
                continue

            # 显示摄像头画面
            cv2.imshow("Camera Test", frame)

            # 按 Q 退出
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

    except Exception as e:
        print("摄像头测试发生错误：", e)

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("摄像头测试结束")


if __name__ == "__main__":
    main()
